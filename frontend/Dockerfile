# ----------- Build Stage -----------
FROM node:lts AS build

WORKDIR /app

# 複製 package.json 與 lock 檔案
COPY package*.json ./

# 安裝依賴
RUN npm install

# 複製所有原始碼
COPY . .

# 編譯前端（假設用 Vite，會產生 dist/）
RUN npm run build

# ----------- Production Stage -----------
FROM nginx:alpine

# 複製 build 後的靜態檔案到 nginx 預設目錄
COPY --from=build /app/dist /usr/share/nginx/html

# 可選：自訂 nginx 設定（如需 history fallback，可自行加入）
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# 開放 80 port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]