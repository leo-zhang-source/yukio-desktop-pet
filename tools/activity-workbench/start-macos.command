#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
python3 -B launcher.py --collect
result=$?
if [ "$result" -ne 0 ]; then
  printf '%s\n' '启动没有完成。请保留上面的提示，按回车关闭。'
  read -r answer
fi
exit "$result"
