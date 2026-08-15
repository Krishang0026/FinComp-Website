# Starts the application using the active Python installation.
# This explicitly exposes user-installed packages for Python installations that
# do not add their user site-packages directory to sys.path automatically.
$ErrorActionPreference = 'Stop'
$userSite = python -c "import site; print(site.getusersitepackages())"
if (-not (Test-Path $userSite)) {
    throw "Python user packages were not found. Run: python -m pip install -r requirements.txt"
}
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$userSite;$env:PYTHONPATH" } else { $userSite }
python -m streamlit run app/main.py
