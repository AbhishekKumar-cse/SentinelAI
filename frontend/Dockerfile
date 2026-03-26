# Use Node.js
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy app
COPY . .

# Build app
RUN npm run build

# Start app
CMD ["npm", "start"]
