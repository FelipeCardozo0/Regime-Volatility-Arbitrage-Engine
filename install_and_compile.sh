#!/bin/bash
# One-command LaTeX installation and compilation

echo "Installing BasicTeX (you'll be prompted for your password)..."
brew install --cask basictex

echo ""
echo "Updating PATH..."
eval "$(/usr/libexec/path_helper)"

echo ""
echo "Installing required LaTeX packages..."
sudo tlmgr update --self
sudo tlmgr install ieeetran

echo ""
echo "Compiling PDF (first pass)..."
pdflatex -interaction=nonstopmode main.tex

echo ""
echo "Compiling PDF (second pass for cross-references)..."
pdflatex -interaction=nonstopmode main.tex

if [ -f main.pdf ]; then
    echo ""
    echo "✓ SUCCESS! PDF created: main.pdf"
else
    echo ""
    echo "✗ Error: PDF was not created."
fi

