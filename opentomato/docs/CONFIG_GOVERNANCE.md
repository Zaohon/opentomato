# 瀵嗛挜涓庨厤缃不鐞嗗熀绾?

## 1. 宸插畬鎴愮殑浠撳簱娌荤悊

- `.env` 宸蹭粠鐗堟湰鎺у埗涓Щ闄わ紙閫氳繃 Git 绱㈠紩鍒犻櫎锛屼繚鐣欐湰鍦版枃浠讹級銆?
- 鏂板 `.gitignore`锛岄粯璁ゅ拷鐣?`.env`銆佽瘉涔﹀拰杩愯浜х墿銆?
- `.env.example` 宸叉墿灞曚负瀹屾暣妯℃澘锛岃鐩栬繍琛屾墍闇€涓昏閰嶇疆椤广€?
- 鍚姩鏃跺鍔犻厤缃牎楠岋細
  - 鎵€鏈夌幆澧冨繀椤昏嚦灏戦厤缃?`DASHSCOPE_API_KEY` 鎴?`DASHSCOPE_API_KEY`銆?
  - 鐢熶骇鐜 (`APP_ENV=production/prod`) 绂佹 `CORS_ALLOW_ORIGINS=*`銆?
  - 鐢熶骇鐜浼氶樆鏂崰浣嶇/榛樿鍊煎瘑閽ュ惎鍔ㄣ€?

## 2. 涓€娆℃€у畨鍏ㄥ缃紙蹇呴』鎵ц锛?

鐢变簬鍘嗗彶涓?`.env` 琚彁浜よ繃锛屼互涓嬪嚟鎹簲瑙嗕负宸叉硠闇插苟绔嬪嵆杞崲锛?

- LLM/API 鐩稿叧瀵嗛挜
- InfluxDB Token
- MySQL 瀵嗙爜
- MQTT 璁块棶瀵嗛挜/瀵嗙爜
- DashVector API Key

瀹屾垚杞崲鍚庯紝鏇存柊鏈湴 `.env`锛屽苟鍦ㄩ儴缃插钩鍙帮紙K8s Secret/浜戝瘑閽ョ鐞嗭級鍚屾鏂板€笺€?

## 3. 鐢熶骇閰嶇疆瑕佹眰

- `APP_ENV=production`
- `CORS_ALLOW_ORIGINS` 蹇呴』鏄槑纭煙鍚嶅垪琛紙閫楀彿鍒嗛殧锛夛紝绀轰緥锛?
  - `https://hems.example.com,https://admin.hems.example.com`
- 绂佹浣跨敤妯℃澘鍗犱綅绗︽垨榛樿娴嬭瘯鍊笺€?

## 4. 鍚姩鍓嶈嚜妫€

搴旂敤浼氬湪 FastAPI 鍚姩鏃惰嚜鍔ㄦ墽琛岄厤缃牎楠岋紱鑻ヤ笉閫氳繃浼氱洿鎺ュけ璐ュ苟杈撳嚭閿欒椤广€?



