import type { Lang } from "../languages";

import { method as bn } from "./bn";
import { method as en, type MethodText } from "./en";
import { method as gu } from "./gu";
import { method as hi } from "./hi";
import { method as mr } from "./mr";
import { method as ta } from "./ta";
import { method as te } from "./te";

export const METHOD: Record<Lang, MethodText> = { en, hi, gu, mr, ta, te, bn };
