FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY index.js .
COPY middleware/ ./middleware/
COPY public/ ./public/
EXPOSE 8080 8443
CMD ["node", "index.js"]
