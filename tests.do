
find . -name '*_test.py' \
| grep -v venv \
| sed 's/_test.py$/.vcd/' \
| xargs redo-ifchange

