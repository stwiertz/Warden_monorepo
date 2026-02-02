/**
 * Expo config plugin for FFmpeg fork integration.
 * Injects native dependencies via expo prebuild.
 *
 * TODO: Implement config plugin for jdarshan5/ffmpeg-kit-react-native fork
 */

const { withProjectBuildGradle } = require('expo/config-plugins');

const withFfmpeg = (config) => {
  // Placeholder - will configure native FFmpeg dependencies
  return config;
};

module.exports = withFfmpeg;
