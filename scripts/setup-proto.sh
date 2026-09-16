#!/bin/bash
set -e

echo "🔧 Setting up Buf and proto toolchain..."

# Check if buf is installed
if ! command -v buf &> /dev/null; then
    echo "❌ Buf CLI not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install bufbuild/buf/buf
    else
        curl -sSL "https://github.com/bufbuild/buf/releases/latest/download/buf-$(uname -s)-$(uname -m)" -o /usr/local/bin/buf
        chmod +x /usr/local/bin/buf
    fi
fi

echo "✅ Buf version: $(buf --version)"

# Check if pnpm is installed
if ! command -v pnpm &> /dev/null; then
    echo "❌ pnpm not found. Installing..."
    npm install -g pnpm@9
fi

echo "✅ pnpm version: $(pnpm --version)"

# Install dependencies
echo "📦 Installing monorepo dependencies..."
pnpm install

# Lint proto files
echo "🔍 Linting proto files..."
cd proto && buf lint && cd ..

# Generate code for all languages
echo "⚙️  Generating code for all languages..."
cd proto && buf generate && cd ..

# Verify generated files
echo "✅ Verifying generated files..."
if [ -d "gen/go" ] && [ "$(ls -A gen/go)" ]; then
    echo "  ✅ Go code generated"
else
    echo "  ❌ Go code generation failed"
    exit 1
fi

if [ -d "gen/rust" ] && [ "$(ls -A gen/rust)" ]; then
    echo "  ✅ Rust code generated"
else
    echo "  ❌ Rust code generation failed"
    exit 1
fi

if [ -d "gen/python" ] && [ "$(ls -A gen/python)" ]; then
    echo "  ✅ Python code generated"
else
    echo "  ❌ Python code generation failed"
    exit 1
fi

if [ -d "apps/dashboard/src/generated" ] && [ "$(ls -A apps/dashboard/src/generated)" ]; then
    echo "  ✅ TypeScript code generated"
else
    echo "  ❌ TypeScript code generation failed"
    exit 1
fi

echo ""
echo "🎉 Proto setup complete!"
echo ""
echo "Next steps:"
echo "  - Run 'pnpm proto:lint' to lint proto files"
echo "  - Run 'pnpm proto:generate' to regenerate code"
echo "  - Run 'pnpm proto:breaking' to check for breaking changes"
echo "  - See proto/README.md for full documentation"
