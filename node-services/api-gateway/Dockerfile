FROM node:lts AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install
# build image 前需確保本地 api-gateway 資料夾內容是最新的。
COPY . .
RUN npm run build

FROM node:lts AS production
WORKDIR /app
COPY package*.json ./
RUN npm install --only=production
COPY --from=builder /app/dist ./dist
CMD ["npm", "run", "start"]
