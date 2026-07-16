FROM node:20-alpine

WORKDIR /app

# 安装依赖
COPY package.json .
RUN npm install

# 复制源码
COPY . .

# 暴露端口
EXPOSE 5173

# 启动开发服务器
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
