import React from "react";
import { Composition } from "remotion";
import { GE01 as C_ge01, built as b_ge01 } from "../episodes/ge01/Video";
import { Video as C_gs004, built as b_gs004 } from "../episodes/gs004/Video";
import { Video as C_gs006, built as b_gs006 } from "../episodes/gs006/Video";
import { Video as C_gs007, built as b_gs007 } from "../episodes/gs007/Video";
import { Video as C_gs008, built as b_gs008 } from "../episodes/gs008/Video";
import { GS01 as C_gs01, built as b_gs01 } from "../episodes/gs01/Video";
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
    <Composition id="GS01" component={C_gs01} durationInFrames={b_gs01.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS02" component={C_gs02} durationInFrames={b_gs02.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS03" component={C_gs03} durationInFrames={b_gs03.total} fps={FPS} width={1080} height={1920} />
  </>
);
