#!/bin/bash
# deploy เว็บแอปขึ้น Hugging Face Space (สาธารณะ)
# ใช้ก่อนหน้านี้ต้อง: huggingface-cli login แล้ว export HF_USER=<ชื่อบัญชี>
set -euo pipefail
cd "$(dirname "$0")"

HF_USER="${HF_USER:?ตั้งค่าชื่อบัญชีก่อน เช่น export HF_USER=yourname}"
SPACE="${SPACE:-thai-transcribe}"

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

cp app.py transcribe.py requirements-web.txt "$STAGE/"
cp requirements-web.txt "$STAGE/requirements.txt"
cp space/README.md "$STAGE/README.md"
printf 'ffmpeg\n' > "$STAGE/packages.txt"

cd "$STAGE"
git init -q -b main
git add -A
GIT_AUTHOR_NAME="deploy" GIT_AUTHOR_EMAIL="deploy@users.noreply.huggingface.co" \
  git commit -qm "deploy thai-transcribe webapp"

# ใช้ token ที่ huggingface-cli login เก็บไว้ (ไม่ต้องพิมพ์รหัสซ้ำ)
PUSH_URL=$(python3 - <<'EOF'
from huggingface_hub import get_token
print(f"https://oauth2:{get_token()}@huggingface.co")
EOF
)
git remote add origin "$PUSH_URL/spaces/$HF_USER/$SPACE"
git push -q -f origin main
echo "✅ deploy แล้ว: https://huggingface.co/spaces/$HF_USER/$SPACE"
