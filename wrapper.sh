#!/bin/bash
pythons=(/bin/python3 /usr/bin/python3 /bin/python /usr/bin/python)
for python in "${pythons[@]}"; do
  if [[ -x $python ]]; then PYTHON=$python; break; fi
done
if [[ -z "$PYTHON" ]]; then
  echo "ERROR: python interpreter was not found, searched in ${pythons[@]}..."
  exit 1
fi
exec $PYTHON - $* <<'EOF'
