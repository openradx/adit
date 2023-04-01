// var addon = require("bindings")("dcmconnector-addon");
const addon = require("./build/Release/dcmconnector-addon");

console.log(addon.hello()); // 'world'
