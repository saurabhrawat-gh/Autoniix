"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.systemApi = void 0;
var client_1 = require("./client");
exports.systemApi = {
    config: function () { return (0, client_1.request)('/api/v2/system/config'); },
    updateConfig: function (config_key, config_value) {
        return (0, client_1.request)('/api/v2/system/config', { method: 'PUT', body: JSON.stringify({ config_key: config_key, config_value: config_value }) });
    },
    emergencyStop: function () { return (0, client_1.request)('/api/v2/system/emergency-stop', { method: 'POST' }); },
    emergencyResume: function () { return (0, client_1.request)('/api/v2/system/emergency-resume', { method: 'POST' }); },
    fleetHealth: function () { return (0, client_1.request)('/api/v2/system/fleet-health'); },
    environment: function () { return (0, client_1.request)('/api/v2/system/environment'); },
    cleanSlate: function () { return (0, client_1.request)('/api/v2/system/clean-slate', { method: 'POST' }); },
};
