
redo-ifchange venv
redo-always

. ./venv.dir/bin/activate
export PYTHONPATH="$(pwd)"

python3 "$2"_test.py >"$3"
