import React from "react";
import { Composition } from "remotion";
import { GE01, built as ge01 } from "../episodes/ge01/Video";
import { GS01, built as gs01 } from "../episodes/gs01/Video";
import { GS02, built as gs02 } from "../episodes/gs02/Video";
import { GS03, built as gs03 } from "../episodes/gs03/Video";
import { FPS } from "./kit/timeline";

export const Root: React.FC = () => (
  <>
    <Composition id="GE01" component={GE01} durationInFrames={ge01.total} fps={FPS} width={1920} height={1080} />
    <Composition id="GS01" component={GS01} durationInFrames={gs01.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS02" component={GS02} durationInFrames={gs02.total} fps={FPS} width={1080} height={1920} />
    <Composition id="GS03" component={GS03} durationInFrames={gs03.total} fps={FPS} width={1080} height={1920} />
  </>
);
