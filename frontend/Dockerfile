FROM node:20-slim as builder

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN VITE_API_URL=https://cerveau-du-parieur-production.up.railway.app npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
