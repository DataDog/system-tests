#!/bin/bash
BASEDIR=$(dirname "$0")

input_file="$BASEDIR/std.in"
output_file="$BASEDIR/std.out"
output_file3="$BASEDIR/std3.out"
[[ -f $input_file ]] || touch $input_file
echo "ls -la" >> $input_file

handle_command() {
  command=$1
  # Execute command

  echo "-----------------------------" >> $output_file
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Executing command: $command  " >> $output_file

  echo "-----------------------------" >> $output_file
  echo "+++++++++++++++++++++++++++++" >> $output_file
  echo " Result                      " >> $output_file
  echo "+++++++++++++++++++++++++++++" >> $output_file

 #$command >> $output_file 2>&1
}

echo "Running krunvm_init.sh"
# Loop to read input file
while true; do
  while IFS= read -r line; do
    if [ -n "$line" ]; then
      handle_command "$line"
      echo "before" >> $output_file3
      # Remove executed command line
      sed -i '1d' "$input_file"
      echo "next" >> $output_file3
    fi
  done < "$input_file"
  sleep 1
done