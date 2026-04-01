const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

// 1. Force project root to be THIS directory only
config.projectRoot = __dirname;

// 2. Explicitly set watch folders to ONLY this directory
config.watchFolders = [__dirname];

// 3. Block list for safety (parent .venv)
config.resolver.blockList = [
    /.*\.venv\/.*/,
    /.*augmented_data.*/,
];

module.exports = config;
