#!/bin/bash
eval "$(/usr/libexec/path_helper)"
echo "Installing missing LaTeX packages (password required)..."
echo "Installing algorithmicx (contains algpseudocode)..."
sudo tlmgr install algorithmicx
echo "Installing caption (contains subcaption)..."
sudo tlmgr install caption
echo "Installing tools (contains bm)..."
sudo tlmgr install tools
echo ""
echo "Compiling PDF..."
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
if [ -f main.pdf ]; then
    echo ""
    echo "✓ SUCCESS! PDF created: main.pdf"
    ls -lh main.pdf
else
    echo ""
    echo "✗ Error: PDF was not created. Check main.log for details."
fi

