package ch4_score

import "core:flags"
import "core:fmt"
import "core:mem"
import "core:os"
import "core:os/os2"
import "core:slice"
import "core:strings"
import "core:text/regex"

Options :: struct {
    grammar: string `args:"pos=0,required" usage:"grammar path"`,
    src: string `args:"pos=1,required" usage:"input path"`,
    tgt: string `args:"pos=2,required" usage:"input path"`,
    target_feats: string `args:"pos=3,required" usage:"target feat regex"`,
    cohorts: int,
    missing: int,
    extra: int,
    ambig: int,
    ins: int,
    unk: int,
    missing_feats: int,
    extra_feats: int,
}

FEATS : regex.Regular_Expression

is_feat :: proc(buf: string) -> bool {
    match, success := regex.match(FEATS, buf)
    defer regex.destroy_capture(match)
    return success
}

read_u16 :: proc(buf: []u8, offset: u16) -> u16 {
    return (u16)(mem.slice_data_cast([]u16le, buf[offset:offset+2])[0])
}

read_u32 :: proc(buf: []u8, offset: u32) -> u32 {
    return (u32)(mem.slice_data_cast([]u32le, buf[offset:offset+4])[0])
}

score_buffer :: proc(src: []byte, tgt: []byte, opt: Options) -> (score: int) {
    word_counts := make(map[string]int)
    defer delete(word_counts)
    feat_counts := make(map[[2]string]int)
    defer delete(feat_counts)
    // SRC
    pos : u16 = 2 // skip flags
    src_tag_count := read_u16(src, pos)
    pos += 2
    src_tags := make([]string, src_tag_count)
    src_feats : [dynamic]u16
    defer delete(src_tags)
    ins_tag : u16 = src_tag_count + 1
    src_tag : u16 = src_tag_count + 1
    size: u16
    for i in 0..<src_tag_count {
	size = read_u16(src, pos)
	pos += 2
	src_tags[i] = transmute(string)src[pos:pos+size]
	if is_feat(src_tags[i]) {
	    append(&src_feats, (u16)(i))
	}
	if ins_tag > src_tag_count && src_tags[i] == "\"<ins>\"" {
	    ins_tag = u16(i)
	} else if src_tag > src_tag_count && src_tags[i] == "SOURCE" {
	    src_tag = u16(i)
	}
	pos += size
    }
    size = read_u16(src, pos)
    pos += 2 + size * 5 // vars
    size = read_u16(src, pos)
    pos += 2 + size // text
    size = read_u16(src, pos)
    pos += 2 + size // text_post
    source_cohorts := read_u16(src, pos)
    pos += 2
    reading_tags : [dynamic]u16
    for cohort_num in 0..<source_cohorts {
	pos += 2 // flags
	surf := read_u16(src, pos)
	pos += 2
	if surf == ins_tag {
	    score += opt.ins
	}
	size = read_u16(src, pos)
	pos += 2 + size * 2 // static tags
	pos += 8 // dep
	size = read_u16(src, pos)
	pos += 2 + size * 6 // rel
	size = read_u16(src, pos)
	pos += 2 + size // text
	size = read_u16(src, pos)
	pos += 2 + size // wblank
	reading_count := read_u16(src, pos)
	pos += 2
	ambig := reading_count
	for reading_num in 0..<reading_count {
	    subreading := (read_u16(src, pos) & 1)
	    pos += 2
	    lem := read_u16(src, pos)
	    pos += 2
	    tag_count := read_u16(src, pos)
	    pos += 2
	    if (subreading != 0 || tag_count == 0) {
		pos += tag_count * 2
		ambig -= 1
		continue
	    }
	    clear(&reading_tags)
	    for tag_num in 0..<tag_count {
		append(&reading_tags, read_u16(src, pos))
		pos += 2
	    }
	    if reading_tags[0] == src_tag {
		ambig -= 1
		continue
	    }
	    if strings.starts_with(src_tags[lem], "\"@") {
		score += opt.unk
	    }
	    key := fmt.aprintf("%s %s", src_tags[lem], src_tags[reading_tags[0]])
	    word_counts[key] += 1
	    for t in reading_tags {
		_, found := slice.binary_search(src_feats[:], t)
		if found {
		    //sub_dict := feat_counts[key]
		    //sub_dict[src_tags[t]] += 1
		    feat_counts[{key, src_tags[t]}] += 1
		}
	    }
	}
	if ambig > 1 {
	    score += opt.ambig * int(ambig - 1)
	}
    }
    // TGT
    pos = 2 // skip flags
    tgt_tag_count := read_u16(tgt, pos)
    pos += 2
    tgt_tags := make([]string, tgt_tag_count)
    tgt_feats : [dynamic]u16
    defer delete(tgt_tags)
    for i in 0..<tgt_tag_count {
	size = read_u16(tgt, pos)
	pos += 2
	tgt_tags[i] = transmute(string)tgt[pos:pos+size]
	if is_feat(tgt_tags[i]) {
	    append(&tgt_feats, (u16)(i))
	}
	pos += size
    }
    size = read_u16(tgt, pos)
    pos += 2 + size * 5 // vars
    size = read_u16(tgt, pos)
    pos += 2 + size // text
    size = read_u16(tgt, pos)
    pos += 2 + size // text_post
    target_cohorts := read_u16(tgt, pos)
    pos += 2
    if (target_cohorts > source_cohorts) {
	score += int(target_cohorts - source_cohorts) * opt.cohorts
    } else {
	score += int(source_cohorts - target_cohorts) * opt.cohorts
    }
    for cohort_num in 0..<target_cohorts {
	pos += 2 // flags
	pos += 2 // surface
	size = read_u16(tgt, pos)
	pos += 2 + size * 2 // static tags
	pos += 8 // dep
	size = read_u16(tgt, pos)
	pos += 2 + size * 6 // rel
	size = read_u16(tgt, pos)
	pos += 2 + size // text
	size = read_u16(tgt, pos)
	pos += 2 + size // wblank
	reading_count := read_u16(tgt, pos)
	pos += 2
	for reading_num in 0..<reading_count {
	    subreading := (read_u16(tgt, pos) & 1)
	    pos += 2
	    lem := read_u16(tgt, pos)
	    pos += 2
	    tag_count := read_u16(tgt, pos)
	    pos += 2
	    if (subreading != 0 || tag_count == 0) {
		pos += tag_count * 2
		continue
	    }
	    clear(&reading_tags)
	    for tag_num in 0..<tag_count {
		append(&reading_tags, read_u16(tgt, pos))
		pos += 2
	    }
	    key := fmt.aprintf("%s %s", tgt_tags[lem], tgt_tags[reading_tags[0]])
	    word_counts[key] -= 1
	    for t in reading_tags {
		_, found := slice.binary_search(tgt_feats[:], t)
		if found {
		    feat_counts[{key, tgt_tags[t]}] -= 1
		}
	    }
	}
    }
    for key in word_counts {
	val := word_counts[key]
	if val > 0 {
	    score += val * opt.extra
	} else {
	    score -= val * opt.missing
	}
    }
    for key in feat_counts {
	val := feat_counts[key]
	if val > 0 {
	    score += val * opt.extra_feats
	} else {
	    score -= val * opt.missing_feats
	}
    }
    return
}

main :: proc() {
    opt: Options
    style : flags.Parsing_Style = .Unix
    flags.parse_or_exit(&opt, os.args, style)

    fmt.println("grammar:", opt.grammar)
    fmt.println("unk:", opt.unk)

    fperr: regex.Error
    FEATS, fperr = regex.create(opt.target_feats)
    defer regex.destroy_regex(FEATS)

    opt.cohorts += 1
    opt.missing += 1
    opt.extra += 1
    opt.ambig += 1
    opt.ins += 1
    opt.unk += 1
    opt.missing_feats += 1
    opt.extra_feats += 1

    fmt.println(opt)

    fmt.println("loading", opt.src)
    src, serr := os2.read_entire_file_from_path(opt.src, context.allocator)
    fmt.println("loading", opt.tgt)
    tgt, terr := os2.read_entire_file_from_path(opt.tgt, context.allocator)

    fmt.println("src", len(src), serr)
    fmt.println("tgt", len(tgt), terr)

    // TODO: pass src through grammar before scoring

    spos : u32 = 8
    tpos : u32 = 8
    slen : u32
    tlen : u32
    score := 0
    windows := 0
    for int(spos) < len(src) && int(tpos) < len(tgt) {
	slen = 0
	for int(spos) < len(src) && src[spos] != 1 {
	    if src[spos] == 2 {
		spos += 2 // command
	    } else {
		spos += 1
		slen = read_u32(src, spos)
		spos += 4 + slen // text
	    }
	}
	if int(spos) >= len(src) {
	    break
	}
	spos += 1
	slen = read_u32(src, spos)
	spos += 4
	tlen = 0
	for int(tpos) < len(tgt) && tgt[tpos] != 1 {
	    if tgt[tpos] == 2 {
		tpos += 2 // command
	    } else {
		tpos += 1
		tlen = read_u32(tgt, tpos)
		tpos += 4 + tlen // text
	    }
	}
	if int(tpos) >= len(tgt) {
	    break
	}
	tpos += 1
	tlen = read_u32(tgt, tpos)
	tpos += 4
	score += score_buffer(src[spos:spos+slen], tgt[tpos:tpos+tlen], opt)
	windows += 1
	spos += slen
	tpos += tlen
    }
    fmt.println("score", score, "windows", windows)
}
