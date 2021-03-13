#! /usr/bin/env bash

#* @file       helper.lib.bash
#* @brief      TODO
#* @details    TODO
#* @auhor      author
#* @copyright  LICENSE
#* @details    TODO

#* License Text

# Moves the cursor back to the start of the line and clears the text on that 
# line
BCK="\r\033[K"

# Internal variables
__spin='-\|/'
__spin_i='0'

function fatal {
    echo "FATAL: $1"
    exit 1
}

function verbose {
    local msg=$1

    if [ "$VERBOSE" = "1" ]; then
        echo $msg | sed 's/^/verbose: /g'
    fi
}

function say {
    local msg=$1

    echo -e $msg
}

function backtrace () {
    local deptn=${#FUNCNAME[@]}

    for ((i=1; i<$deptn; i++)); do
        local func="${FUNCNAME[$i]}"
        local line="${BASH_LINENO[$((i-1))]}"
        local src="${BASH_SOURCE[$((i-1))]}"
        printf '%*s' $i '' # indent
        echo "at: $func(), $src, line $line"
    done
}

function trace_top_caller () {
    local func="${FUNCNAME[1]}"
    local line="${BASH_LINENO[0]}"
    local src="${BASH_SOURCE[0]}"
    echo "  called from: $func(), $src, line $line"
}

function secs2human {
    if [[ -z ${1} || ${1} -lt 60 ]] ;then
        min=0 ; secs="${1}"
    else
        time_mins=$(echo "scale=2; ${1}/60" | bc)
        min=$(echo ${time_mins} | cut -d'.' -f1)
        secs="0.$(echo ${time_mins} | cut -d'.' -f2)"
        secs=$(echo ${secs}*60|bc|awk '{print int($1+0.5)}')
    fi
    echo "${min}m ${secs}s"
}

function hasparent {
    local fname=$1

    basename "$fname" | sed 's/.testcase//g' | egrep -q '\.|,'
    local result=$?

    return $result
}

# Retuns the name of the corresponding pm map file for a testcase
function getpmmapf {
    local tc=$1
    echo "$(dirname $tc)/pm_map_$(basename $tc)"
}

function getparentname {
    local fname=$1

    # Get basename and remove the extension
    bname=$(basename "$fname")
    bname=$(echo "$bname" | sed 's|.testcase||g')

    # Keep everything until last , or .
    pname=$(echo "$bname" | egrep -o '.+[,\.]') 
    pname=${pname%?} # Remove the last character

    echo "$pname.testcase"
}

function getparentimgname {
    local fpath=$1

    pname=$(getparentname "$fpath")
    imgname=$(echo "$pname" | sed 's|.testcase|.*.tar.gz|g')

    echo "$imgname"
}

function testhasparent {
    assertEquals "0" `hasparent '/tmp,,/id=000922,id=000142.testcase' \
        && echo 0 || echo 1`
    assertEquals "1" `hasparent '/tmp,,/id=000142.testcase' \
        && echo 0 || echo 1`
}

function testgetparentname {
    answer=`getparentname /tmp,,/id=000922,id=000142.testcase`
    assertEquals "id=000922.testcase" "$answer"

    answer=`getparentname /tmp,,/id=000922,id=000142.id=000142.testcase`
    assertEquals "id=000922,id=000142.testcase" "$answer"

    answer=`getparentname /tmp,,/id=922.id=142.id=142.testcase`
    assertEquals "id=922.id=142.testcase" "$answer"
}

function testparentimgname {
    answer=`getparentimgname /tmp,,/id=000922,id=000142.testcase`
    assertEquals "id=000922.*.tar.gz" "$answer"

    answer=`getparentimgname /tmp,,/id=000922,id=000142.id=000142.testcase`
    assertEquals "id=000922,id=000142.*.tar.gz" "$answer"

    answer=`getparentimgname /tmp,,/id=922.id=142.id=142.testcase`
    assertEquals "id=922.id=142.*.tar.gz" "$answer"
}

# Run tests only if the script is not being sourced
[[ $1 == "runtest" ]]  && {
    set -- # reset the variable
    . ./vendor/shunit2
}
