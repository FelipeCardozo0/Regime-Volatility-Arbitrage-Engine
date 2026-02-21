#!/bin/bash
# Simple PDF compilation script - run this after BasicTeX is installed

eval "$(/usr/libexec/path_helper)"

if ! command -v pdflatex &> /dev/null; then
    echo "Error: pdflatex not found."
    echo "Please ensure BasicTeX installation is complete, then restart terminal or run:"
    echo "  eval \"\$(/usr/libexec/path_helper)\""
    exit 1
fi

# Install packages if needed
echo "Installing required LaTeX packages..."
sudo tlmgr update --self 2>/dev/null
sudo tlmgr install ieeetran algorithms listings subcaption multirow siunitx microtype enumitem mathtools bm 2>/dev/null

# Compile
echo "Compiling PDF..."
pdflatex -interaction=nonstopmode main.tex > /dev/null 2>&1
pdflatex -interaction=nonstopmode main.tex

if [ -f main.pdf ]; then
    echo ""
    echo "✓ PDF created: main.pdf"
    ls -lh main.pdf
else
    echo "Error: Check main.log for details"
fi

