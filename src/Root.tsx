import React from "react";
import { Composition } from "remotion";
import { GE01 as C_ge01, built as b_ge01 } from "../episodes/ge01/Video";
import { Video as C_gs004, built as b_gs004 } from "../episodes/gs004/Video";
import { Video as C_gs006, built as b_gs006 } from "../episodes/gs006/Video";
import { Video as C_gs007, built as b_gs007 } from "../episodes/gs007/Video";
import { Video as C_gs008, built as b_gs008 } from "../episodes/gs008/Video";
import { Video as C_gs009, built as b_gs009 } from "../episodes/gs009/Video";
import { GS01 as C_gs01, built as b_gs01 } from "../episodes/gs01/Video";
import { Video as C_gs010, built as b_gs010 } from "../episodes/gs010/Video";
import { Video as C_gs011, built as b_gs011 } from "../episodes/gs011/Video";
import { Video as C_gs012, built as b_gs012 } from "../episodes/gs012/Video";
import { Video as C_gs013, built as b_gs013 } from "../episodes/gs013/Video";
import { Video as C_gs014, built as b_gs014 } from "../episodes/gs014/Video";
import { Video as C_gs015, built as b_gs015 } from "../episodes/gs015/Video";
import { Video as C_gs016, built as b_gs016 } from "../episodes/gs016/Video";
import { Video as C_gs017, built as b_gs017 } from "../episodes/gs017/Video";
import { Video as C_gs018, built as b_gs018 } from "../episodes/gs018/Video";
import { Video as C_gs019, built as b_gs019 } from "../episodes/gs019/Video";
import { GS02 as C_gs02, built as b_gs02 } from "../episodes/gs02/Video";
import { GS03 as C_gs03, built as b_gs03 } from "../episodes/gs03/Video";
import { FPS } from "./kit/timeline";

export const Root: React.FC = () => (
  <>
    <Composition id="GE01" component={C_ge01} durationInFrames={b_ge01.total} fps={FPS} width={1920} height={1080} />
    <Composition id="GS004" component={C_gs004} durationInFrames={b_gs004.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS006" component={C_gs006} durationInFrames={b_gs006.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS007" component={C_gs007} durationInFrames={b_gs007.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS008" component={C_gs008} durationInFrames={b_gs008.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS009" component={C_gs009} durationInFrames={b_gs009.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS01" component={C_gs01} durationInFrames={b_gs01.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS010" component={C_gs010} durationInFrames={b_gs010.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS011" component={C_gs011} durationInFrames={b_gs011.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS012" component={C_gs012} durationInFrames={b_gs012.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS013" component={C_gs013} durationInFrames={b_gs013.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS014" component={C_gs014} durationInFrames={b_gs014.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS015" component={C_gs015} durationInFrames={b_gs015.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS016" component={C_gs016} durationInFrames={b_gs016.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS017" component={C_gs017} durationInFrames={b_gs017.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS018" component={C_gs018} durationInFrames={b_gs018.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS019" component={C_gs019} durationInFrames={b_gs019.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS02" component={C_gs02} durationInFrames={b_gs02.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS03" component={C_gs03} durationInFrames={b_gs03.total} fps={FPS} width={1080} height={1920} />
  </>
);
