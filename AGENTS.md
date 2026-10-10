Python Environment

This project uses the local Python virtual environment in the env directory.

Always use the project’s local virtual environment instead of the system Python or global Python environment.

* Python: ./env/bin/python
* pip: ./env/bin/pip

When running Python commands, use:

./env/bin/python

When installing dependencies, use:

./env/bin/pip install ...

Do not use the system python, python3, pip, or pip3 for project commands.

If the env virtual environment does not exist, create it with:

python3 -m venv env

After creating it, all project Python commands and dependency installations must use ./env/bin/python and ./env/bin/pip.