package ch4_pipe_score

import "core:flags"
import "core:fmt"
import "core:mem"
import "core:os"
import "core:os/os2"
import "core:slice"
import "core:strings"

Options :: struct {
    grammar: string `args:"pos=0,required" usage:"grammar path"`,
    src: string `args:"pos=1,required" usage:"input path"`,
    tgt: string `args:"pos=2,required" usage:"input path"`,
    target_lang: string `args:"pos=3,required" usage:"target lang code"`,
    count_feats: bool,
    output: string,
}

LANG :: enum {
    BLX,
    ENG,
    GRC,
}

CURRENT_LANG := LANG.ENG

is_feat :: proc(buf: string) -> bool {
    if len(buf) == 0 {
	return false
    }
    switch CURRENT_LANG {
    case .BLX:
	switch buf[0] {
	case 'A':
	    return (strings.starts_with(buf, "Adjz=") ||
		    strings.starts_with(buf, "Aspect="))
	case 'C':
	    return strings.starts_with(buf, "Caus=")
	case 'D':
	    return strings.starts_with(buf, "Degree=")
	case 'E':
	    return strings.starts_with(buf, "Emph=")
	case 'L':
	    return strings.starts_with(buf, "Loc=")
	case 'M':
	    return strings.starts_with(buf, "Mood=")
	case 'N':
	    return (strings.starts_with(buf, "Nmlz=") ||
		    strings.starts_with(buf, "NumType=") ||
		    strings.starts_with(buf, "Number="))
	case 'P':
	    return (strings.starts_with(buf, "Pluraction=") ||
		    strings.starts_with(buf, "Polarity=") ||
		    strings.starts_with(buf, "Poss="))
	case 'R':
	    return strings.starts_with(buf, "Redup=")
	case 'V':
	    return strings.starts_with(buf, "Voice=")
	}
    case .ENG:
	switch buf[0] {
	case 'A':
	    return strings.starts_with(buf, "Animacy=")
	case 'C':
	    return strings.starts_with(buf, "Case=")
	case 'D':
	    return (strings.starts_with(buf, "Definite=") ||
		    strings.starts_with(buf, "Degree="))
	case 'G':
	    return strings.starts_with(buf, "Gender=")
	case 'L':
	    return strings.starts_with(buf, "LexCat=")
	case 'M':
	    return strings.starts_with(buf, "Mood=")
	case 'N':
	    return (strings.starts_with(buf, "Number=") ||
		    strings.starts_with(buf, "NumType="))
	case 'P':
	    return (strings.starts_with(buf, "Person=") ||
		    strings.starts_with(buf, "PronType="))
	case 'T':
	    return strings.starts_with(buf, "Tense=")
	case 'V':
	    return strings.starts_with(buf, "VerbForm=")
	}
    case .GRC:
	switch buf[0] {
	case 'A':
	    return strings.starts_with(buf, "Aspect=")
	case 'C':
	    return strings.starts_with(buf, "Case=")
	case 'D':
	    return (strings.starts_with(buf, "Definite=") ||
		    strings.starts_with(buf, "Degree="))
	case 'E':
	    return strings.starts_with(buf, "ExtPos=")
	case 'G':
	    return strings.starts_with(buf, "Gender=")
	case 'M':
	    return strings.starts_with(buf, "Mood=")
	case 'N':
	    return (strings.starts_with(buf, "NumType=") ||
		    strings.starts_with(buf, "Number="))
	case 'P':
	    return (strings.starts_with(buf, "Person=") ||
		    strings.starts_with(buf, "Polarity=") ||
		    strings.starts_with(buf, "Poss=") ||
		    strings.starts_with(buf, "PronType="))
	case 'R':
	    return strings.starts_with(buf, "Reflex=")
	case 'T':
	    return strings.starts_with(buf, "Tense=")
	case 'V':
	    return (strings.starts_with(buf, "VerbForm=") ||
		    strings.starts_with(buf, "Voice="))
	}
    }
    return false
}

read_u16 :: proc(buf: []u8, offset: u16) -> u16 {
    return (u16)(mem.slice_data_cast([]u16le, buf[offset:offset+2])[0])
}

read_u32 :: proc(buf: []u8, offset: u32) -> u32 {
    return (u32)(mem.slice_data_cast([]u32le, buf[offset:offset+4])[0])
}

score_buffer :: proc(src: []byte, tgt: []byte, opt: Options) -> (score: int) {
    word_counts := make(map[[2]string]int)
    feat_counts := make(map[[3]string]int)
    // SRC
    pos : u16 = 2 // skip flags
    src_tag_count := read_u16(src, pos)
    pos += 2
    src_tags := make([]string, src_tag_count)
    src_feats : [dynamic]u16
    src_tag : u16 = src_tag_count + 1
    size: u16
    for i in 0..<src_tag_count {
	size = read_u16(src, pos)
	pos += 2
	src_tags[i] = transmute(string)src[pos:pos+size]
	if opt.count_feats && is_feat(src_tags[i]) {
	    append(&src_feats, (u16)(i))
	}
	if src_tag > src_tag_count && src_tags[i] == "SOURCE" {
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
	pos += 2 // surf
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
	for reading_num in 0..<reading_count {
	    subreading := (read_u16(src, pos) & 1)
	    pos += 2
	    lem := read_u16(src, pos)
	    pos += 2
	    tag_count := read_u16(src, pos)
	    pos += 2
	    if (subreading != 0 || tag_count == 0) {
		pos += tag_count * 2
		continue
	    }
	    clear(&reading_tags)
	    for tag_num in 0..<tag_count {
		append(&reading_tags, read_u16(src, pos))
		pos += 2
	    }
	    if reading_tags[0] == src_tag {
		continue
	    }
	    if !opt.count_feats {
		word_counts[{src_tags[lem], src_tags[reading_tags[0]]}] += 1
	    } else {
		for t in reading_tags {
		    _, found := slice.binary_search(src_feats[:], t)
		    if found {
			feat_counts[{src_tags[lem], src_tags[reading_tags[0]], src_tags[t]}] += 1
		    }
		}
	    }
	}
    }
    // TGT
    pos = 2 // skip flags
    tgt_tag_count := read_u16(tgt, pos)
    pos += 2
    tgt_tags := make([]string, tgt_tag_count)
    tgt_feats : [dynamic]u16
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
	    if !opt.count_feats {
		word_counts[{tgt_tags[lem], tgt_tags[reading_tags[0]]}] -= 1
	    } else {
		for t in reading_tags {
		    _, found := slice.binary_search(tgt_feats[:], t)
		    if found {
			feat_counts[{tgt_tags[lem], tgt_tags[reading_tags[0]], tgt_tags[t]}] -= 1
		    }
		}
	    }
	}
    }
    for key, val in word_counts {
	score += abs(val)
    }
    for key, val in feat_counts {
	score += abs(val)
    }
    return
}

main :: proc() {
    opt: Options
    style : flags.Parsing_Style = .Unix
    flags.parse_or_exit(&opt, os.args, style)

    switch opt.target_lang {
    case "blx":
	CURRENT_LANG = .BLX
    case "eng":
	CURRENT_LANG = .ENG
    case "grc":
	CURRENT_LANG = .GRC
    }

    state, src, stderr, serr := os2.process_exec({
	command = {"vislcg3", "-g", opt.grammar, "-I", opt.src,
		   "--in-binary", "--out-binary"},
    }, context.allocator)
    //fmt.println(transmute(string)stderr)
    defer delete(src)
    defer delete(stderr)

    tgt, terr := os2.read_entire_file_from_path(opt.tgt, context.allocator)
    defer delete(tgt)

    arena_data := make([]u8, mem.Megabyte)
    arena: mem.Arena
    mem.arena_init(&arena, arena_data)
    context.allocator = mem.arena_allocator(&arena)

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
	mem.arena_free_all(&arena)
    }
    fmt.println("score", score, "windows", windows)
    if len(opt.output) > 0 {
	we := os2.write_entire_file_from_bytes(opt.output, src)
	fmt.eprintln("status:", we)
    }
}
