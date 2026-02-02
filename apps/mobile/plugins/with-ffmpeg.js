const { withAppBuildGradle } = require("expo/config-plugins");

/**
 * Expo config plugin to integrate jdarshan5/ffmpeg-kit-react-native.
 *
 * This plugin modifies the Android app/build.gradle to add the FFmpeg
 * dependency from the community fork (the official ffmpeg-kit was deprecated
 * in Jan 2025 and archived Jun 2025).
 *
 * Usage in app.json / app.config.ts:
 *   plugins: ["./plugins/with-ffmpeg"]
 */
function withFFmpeg(config) {
  return withAppBuildGradle(config, (config) => {
    const buildGradle = config.modResults.contents;

    // Add FFmpeg dependency if not already present
    if (!buildGradle.includes("ffmpeg-kit-react-native")) {
      config.modResults.contents = buildGradle.replace(
        /dependencies\s*{/,
        `dependencies {
    implementation 'com.github.jdarshan5:ffmpeg-kit-react-native:6.0-2'`
      );
    }

    return config;
  });
}

module.exports = withFFmpeg;
