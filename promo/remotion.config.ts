import { Config } from '@remotion/cli/config';
Config.setVideoImageFormat('jpeg');
Config.setBrowserExecutable(process.env.CHROME_PATH || '/usr/bin/google-chrome');
Config.setConcurrency(8);
Config.setCodec('h264');
Config.setCrf(18);
