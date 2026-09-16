"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.usersApi = void 0;
var client_1 = require("./client");
exports.usersApi = {
    list: function () { return (0, client_1.request)('/api/v2/users'); },
    transferSuperadmin: function (targetId) {
        return (0, client_1.request)("/api/v2/users/transfer-superadmin/".concat(targetId), { method: 'POST' });
    },
    disable: function (id) { return (0, client_1.request)("/api/v2/users/".concat(id, "/disable"), { method: 'PUT' }); },
    enable: function (id) { return (0, client_1.request)("/api/v2/users/".concat(id, "/enable"), { method: 'PUT' }); },
    delete: function (id) { return (0, client_1.request)("/api/v2/users/".concat(id), { method: 'DELETE' }); },
};
