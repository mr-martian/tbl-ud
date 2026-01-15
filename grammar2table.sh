#!/bin/bash

grep '#' | grep : | sed 's/[:%]//g' | sed 's/ /\t/g' | cut -f2,3,5,7
