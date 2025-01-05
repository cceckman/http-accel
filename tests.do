
ls *_test.py \
| sed 's/_test.py$/.vcd/' \
| xargs redo-ifchange

