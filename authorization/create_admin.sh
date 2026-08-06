#!/bin/sh
TOKEN=$(curl -s -X POST http://localhost:8080/guacamole/api/tokens \
  -d "username=guacadmin&password=guacadmin" \
  | sed -n 's/.*"authToken":"\([^"]*\)".*/\1/p')

echo "Token: $TOKEN"

curl -s -X POST \
  "http://localhost:8080/guacamole/api/session/data/postgresql/users?token=$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","attributes":{}}'

curl -s -X PUT \
  "http://localhost:8080/guacamole/api/session/data/postgresql/users/admin/password?token=$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"oldPassword":"","newPassword":"admin123"}'