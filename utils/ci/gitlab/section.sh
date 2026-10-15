# shellcheck shell=bash
# function for starting the section
function section_start () {
  local section_title="${1}"
  local section_description="${2:-$section_title}"
  local fold_section="${3:-true}"

  echo -e "section_start:$(date +%s):${section_title}[collapsed=${fold_section}]\r\e[0K${section_description}"
}

# Function for ending the section
function section_end () {
  local section_title="${1}"

  echo -e "section_end:$(date +%s):${section_title}\r\e[0K"
}
