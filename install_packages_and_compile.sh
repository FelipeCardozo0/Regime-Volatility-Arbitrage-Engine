#!/bin/bash
eval "$(/usr/libexec/path_helper)"
echo "Installing missing LaTeX packages (password required)..."
sudo tlmgr install algorithmicx caption tools collection-fontsrecommended
echo ""
echo "Compiling PDF..."
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
if [ -f main.pdf ]; then
    echo ""
    echo "✓ PDF created: main.pdf"
    ls -lh main.pdf
else
    echo "Error: Check main.log"
fi

