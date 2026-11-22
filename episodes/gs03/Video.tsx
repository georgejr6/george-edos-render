import script from "./script.json";
import timing from "./timing.json";
import { makeTutorial, TScript } from "../../src/kit/tutorial";
import { Timing } from "../../src/kit/timeline";

export const { Comp: GS03, built } = makeTutorial(script as unknown as TScript, timing as Timing);
