
redo-ifchange venv
redo-always

. ./venv.dir/bin/activate
python3 "$2"_test.py >"$3"
