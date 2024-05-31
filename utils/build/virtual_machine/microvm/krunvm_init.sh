#!/bin/bash
BASEDIR=$(dirname "$0")

input_file="$BASEDIR/std.in"
output_file="$BASEDIR/std.out"
[[ -f $input_file ]] || touch $input_file
echo "ls -la" >> $input_file

handle_command() {
  command=$1
  # Execute command

  echo "    " >> $output_file
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Executing command: $command  " >> $output_file
  [[ $(echo $command | xargs) == \#* ]] && return
  #echo "-----------------------------" >> $output_file
  #echo "+++++++++++++++++++++++++++++" >> $output_file
  #echo " Result                      " >> $output_file
  #echo "+++++++++++++++++++++++++++++" >> $output_file
  (eval $command  | sed s/^/"       "/ >> $output_file) 2>&1 | sed s/^/"        err:"/ >> $output_file
 #  $command >> $output_file 2>&1 
}

echo "Running krunvm_init.sh"
# Loop to read input file
while true; do
  while IFS= read -r line; do
    if [ -n "$line" ]; then
      handle_command "$line"
      # Remove executed command line
      sed -i '1d' "$input_file"
    fi
  done < <(grep . "${input_file}")
  sleep 1
done