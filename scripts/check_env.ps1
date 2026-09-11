Write-Host "Python:"
python --version

Write-Host "Executable:"
python -c "import sys; print(sys.executable)"

Write-Host "Cargo:"
cargo --version

Write-Host "Maturin:"
maturin --version