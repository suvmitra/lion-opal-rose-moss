# 01_changelog.py — shared engine namespace (do not import directly)

# ------------------------------------------------------------------------------
# Version/state tracking
# ------------------------------------------------------------------------------

CHANGELOG = {
    "24.0.113": [
        "Participate taps the green pill CENTER (y~860), never the Android nav at y=899/2776.",
        "SAFE TAP clamps Participate instead of refusing. WebView click on the landing CTA.",
    ],
    "24.0.112": [
        "Dublin orange (even if OCR misses white-on-orange) then ONLY scroll down to Continue.",
        "Never scroll back up after Dublin is chosen. Open list after the tap is success.",
    ],
    "24.0.111": [
        "Open county list: tap Dublin, never rewrite to Continue at y=610 (that was Kerry).",
        "Orange Kerry is not a completed answer. Scroll until the footer Continue (y>=860).",
    ],
    "24.0.110": [
        "Continue from OCR text still grounds when there is no screenshot (MaxDiff self-check).",
        "Sticky orange footer (y~910) still wins over a county row when the screenshot exists.",
    ],
    "24.0.109": [
        "County picked flag must not leak into later self-checks or unrelated screens.",
        "RL replay of Hovis select-one works again after the county module.",
    ],
    "24.0.108": [
        "Continue is the LOWEST orange bar (~y=910), never the selected county row at y=780 (Wexford).",
        "RL replay cannot click y=780 on a county list. Footer Continue is allowed at y>0.86.",
    ],
    "24.0.107": [
        "Dublin already orange: stop hunting the list. Scroll down until Continue, then tap it.",
        "Orange selected row is the answer; Galway-first OCR must not scroll back up.",
    ],
    "24.0.106": [
        "After 44 is typed, hide the keyboard and tap Continue. Never type a second 44.",
        "Keyboard visible + typed session = Continue, even if crop OCR still looks empty.",
    ],
    "24.0.105": [
        "Age tap is the white box ~55 milli above Continue (y≈418), not the 'no more than 99' error at y=380.",
        "Crop OCR ignores banner 99. Empty box + error still types 44. Continue once the box is exactly 44.",
    ],
    "24.0.104": [
        "Screenshot-first THINK: SEE the box/error, THEREFORE act. VLM reads 4444 when Tesseract misses it.",
        "Continue only after the model or crop OCR confirms the box is exactly 44.",
    ],
    "24.0.103": [
        "Age box is OCR'd from the screenshot crop: 4444 / 'no more than 99' is replaced with 44 before Continue.",
        "typed=True no longer skips a bad value. Continue uses the orange bar at y<=520, not the gray slab.",
    ],
    "24.0.102": [
        "Age is typed once (44), never 4444. Then hide keyboard and tap orange Continue.",
        "Red 'whole number' banner is not treated as an empty field after 44 is visible.",
    ],
    "24.0.101": [
        "Age box is the rounded field ABOVE the orange Continue bar, not the gray slab at y=603.",
        "Type 44 with digit keyevents into the WebView, then tap Continue. ui.xml/Aloha dump has no Qualtrics field.",
    ],
    "24.0.100": [
        "What is your age? types knowledge_base age=44 into the empty box, then the orange Continue bar.",
        "Whole-number validation is adult age, not child_age=8. RL/VLM cannot Continue on an empty field.",
    ],
    "24.0.99": [
        "Card gender (Are you...?) taps Male then mid-screen Continue. Radio-list Are you? still fills Male before Continue.",
        "Startup Are-you inspector self-check is restored.",
    ],
    "24.0.98": [
        "Gender cards: tap Male at the upper-left card (~y=280), then orange Continue at ~y=455.",
        "Never re-tap Male, never scroll, never tap y=875 gray. Learned coords [274,709] ignored.",
    ],
    "24.0.97": [
        "Selected Male + visible Continue: tap Continue once. Do not re-tap Male (toggle off).",
        "Learned click is treated like select_option. Continue OCR includes mid-screen orange bars.",
    ],
    "24.0.96": [
        "Tap the screenshot word Continue (OCR box, inverted footer if white-on-orange).",
        "Never use UI dump node 84 at y=920; that is the Android nav, not the orange bar.",
    ],
    "24.0.95": [
        "I Agree already orange: tap full-width Continue at y~890, never Next [154,626] or nav 920.",
        "Clamp 870 was the gray gap above Continue; cycle 890/882/898 and WebView+native tap.",
    ],
    "24.0.94": [
        "Choreograph I-Agree screen: never let prefer_progression replace Gemini's tap.",
        "If I Agree is already orange, tap the LOWER orange Continue bar (~y=888), not dump-node 920.",
    ],
    "24.0.93": [
        "OCR '| Agree' still matches I Agree; route before RL scroll/Next.",
        "Fix TypeError int(list) on Continue coords; clamp dump-node y=92% to 870.",
    ],
    "24.0.92": [
        "I Agree / I Decline: tap I Agree then orange Continue. Do not let prefer_progression replace Gemini's I Agree with a nav-bar Continue.",
        "Empty-target VLM clicks are kept when they land on I Agree (~y=78%).",
    ],
    "24.0.91": [
        "Fix NameError: main is not defined. Parts no longer run as __main__ during load.",
        "Clear error if survey_engine/parts/25_runner.py is missing.",
    ],
    "24.0.90": [
        "Failed taps go to Gemini with the screenshot (WH: who/what/why/how/when). Do not halt until the image LLM has tried.",
        "Local routers no longer skip vision after a miss; failed coordinates are not repeated.",
    ],
    "24.0.89": [
        "Start! taps the green pill at ~y=40%, not the word start in the instruction sentence.",
        "WebView click on Start!. Misses retarget the pill; recovery does not scroll the landing away.",
    ],
    "24.0.88": [
        "Split the 14k-line runner into survey_engine/parts (max 800 lines each) loaded into one namespace.",
        "python survey_with_salad.py is unchanged; every function is preserved.",
    ],
    "24.0.87": [
        "Start! gate: tap the green Start button (not Continue at y=78% empty space).",
        "Navigation uses the landing CTA before RL replay. Gemini still sees the screenshot when routers miss.",
    ],
    "24.0.86": [
        "Qualified landing Participate is tapped at screenshot coords [500,900], not dump node y=2764.",
        "SAFE TAP allows Participate/Get started up to 93.5% of the screen (above the system nav bar).",
    ],
    "24.0.85": [
        "Select-one: detect gray option rows from pixels, tap the radio circle, then Continue in the same action.",
        "WebView click uses tap + touchscreen tap + motionevent (swipe-hold was ignored by Chrome).",
        "Do not require the red banner to vanish before Continue.",
    ],
    "24.0.84": [
        "Select-one taps the gray-row center (OCR in the body), then Continue; red banner is expected until Continue.",
        "Missed taps retarget x/y, then TAB/SPACE/ENTER. Inspector no longer blocks Continue after a real tap.",
        "Authoritative option taps use a 160ms press so the WebView registers them.",
    ],
    "24.0.83": [
        "Please select an answer always taps the first radio at row coords; the green Continue pill is not a selected radio.",
        "Inspector no longer strips those coords or OCR-taps the Android nav bar.",
        "Lime-band scan stops above the Continue pill (y<72%).",
    ],
    "24.0.82": [
        "Generalized widget router: unseen Select-one / Select-all / text / Continue screens get an assumed action instead of landing-Continue.",
        "RL policy in knowledge_base.json: Q-values by widget class + question stem; router wins are stored and replayed.",
        "Learning ignores clock/banner in the stem; failed Continue-with-empty-payload is punished.",
    ],
    "24.0.81": [
        "'Select one' radio pages are questions, not landing. Tap Buy another brand of bread then Continue.",
        "Never click Continue with payload=None while Please select an answer is showing.",
        "ASK block tells the model the empty radio and required option payload.",
    ],
    "24.0.80": [
        "Lime/green checkbox rows mean the select-all task is done. Scroll to Continue and tap it; never retap a green row.",
        "Stale 'you selected 0' / red banner is ignored when a green tick is visible.",
        "Screen-task gate: if the page already has answers, discover Continue (scroll if needed) instead of looping taps.",
    ],
    "24.0.79": [
        "Brand checkboxes are tapped on the gray rows (Johnson y~58%, Brennans y~66%), not the question title at y=36%.",
        "Duplicate Johnson labels are collapsed; Brennans is always in the plan. Missed taps are not marked done.",
        "While 'you selected 0' is visible, never Continue and never retap the same missed coordinate.",
    ],
    "24.0.78": [
        "Brand 'select all that apply' ticks Brennans / Johnson Mooney from the KB, then Continue. Never Continue while 'you selected 0'.",
        "Each select-all screen has its own session; claims ticks do not carry onto the brand list.",
        "Open-text does not steal checkbox pages (select all that apply / at least 1 answer).",
    ],
    "24.0.77": [
        "Open-text answers are short and human (Batch, Pat the Baker, SuperValu) — never the AI filler sentence.",
        "Type once, Continue once, mark the screen done; never append into the same box.",
        "Chrome/WebView is a valid survey foreground; do not relaunch the app and wipe the form.",
    ],
    "24.0.76": [
        "Continue keeps the dump node id for self-checks; screenshot green-pill coords are authoritative when a screenshot exists.",
        "Preflight progression check no longer blocks the run.",
    ],
    "24.0.75": [
        "Follow-up '...any other brand?' is a NEW empty box; previous Brennans heading is not the current answer.",
        "Red 'Please provide an answer' types extra brands (Batch, Pat the Baker) then taps the green Continue pill by screenshot coords, never dump node 22.",
        "LLM ASK= block states the visible question, validation error, and empty-field instruction.",
    ],
    "24.0.74": [
        "Salad 404/5xx is marked offline for the rest of the run; Gemini stays primary. If Gemini is also down, ask the operator to start Salad.",
        "Bread-brand comment box: type Brennans/Johnston Mooney once (ADB-safe, no apostrophe), never retap the keyboard.",
        "With the keyboard up, Continue is the green pill above it (~y=50%), not coords y=76%.",
    ],
    "24.0.73": [
        "Select-all-that-apply: plan 2 claims, never retap a green row, scroll to Continue, never ask the terminal.",
        "Minimum two ticked boxes then Continue — Other please specify is skipped.",
        "Human prompt is blocked on claim checklists; local router owns the screen.",
    ],
    "24.0.72": [
        "Cycle time cut ~50%: cache Tesseract line OCR, skip inspect re-OCR on MaxDiff, light verify (no UI dump).",
        "Device size and foreground checks are cached; post-tap wait 1.5s → 0.7s.",
        "MaxDiff row Y comes from one OCR pass, not one Tesseract run per label.",
    ],
    "24.0.71": [
        "MaxDiff session key is Screen N of M only — clock/OCR noise must not wipe Most/Least.",
        "Never retap Least after it is issued; that unchecks the green radio. Next action is Continue.",
        "Least radio is scanned in the right 75–96% band; Continue pill is tapped when visible.",
    ],
    "24.0.70": [
        "MaxDiff Continue is often below the table — scroll until the green pill is actually on screen.",
        "Never tap a phantom Continue at y=86% (Android nav bar). Same-screen miss forces another scroll.",
        "Session key includes Screen N of M so page 2 does not inherit page 1 Most/Least.",
    ],
    "24.0.69": [
        "MaxDiff Most/Least: pick ONE Most and a DIFFERENT Least, then Continue — never fill every row.",
        "Local maxdiff router runs before the VLM so a 0.00-confidence dump cannot open a human prompt.",
        "Retapping Most is forbidden; it moves the green dot off the first choice.",
    ],
    "24.0.68": [
        "Thanks card with no gray rows always taps green Continue — leftover red banner is not a reason to step left.",
        "A failed left-chevron tap marks review_done so the next cycle hits Continue instead of stagnating.",
        "Chevron Y uses the thanks-text band (~50%), never the 33% title/banner band.",
    ],
    "24.0.67": [
        "Thanks-for-those-answers card taps green Continue, never a dead right chevron.",
        "Red banner on that card: tap the left chevron, fill any gray row, then Continue.",
        "A full lime progress bar is not a selected answer; option tiles must be wide AND tall.",
    ],
    "24.0.66": [
        "Preflight age self-check: empty test KB must not pick age 44 from disk.",
        "Live observe() always loads knowledge_base.json so child_age=8 is present.",
    ],
    "24.0.65": [
        "Please state their ages types knowledge_base child_age=8; do not ask the terminal.",
        "Human prompt is once per fact key. Inspect/repair/self-check cannot reprint it.",
        "Reload knowledge_base.json from disk before treating child_age as missing.",
    ],
    "24.0.64": [
        "Carousel taps the gray option tiles below the title, not the Baps label at y=52%.",
        "Red banner on a carousel is expected until every row is answered — do not fail verify.",
        "Never rewrite a missed carousel tap into Continue.",
    ],
    "24.0.63": [
        "Carousel item is the centered title (Bagels/Baps), never banner or Help footer.",
        "If a row is green-selected, tap the right chevron at the item Y — not Continue.",
        "Continue only when the green progress bar is nearly full (or the right chevron is dead).",
    ],
    "24.0.62": [
        "Bread carousel: answer the current item, tap the right arrow, only Continue on the last item.",
        "Do not treat 'Select one in each row' as a single Continue click.",
        "Gemini tries 3.5-flash-lite first; skip 404/retired 2.5 names for the rest of the run.",
    ],
    "24.0.61": [
        "Please state their ages: type knowledge_base child_age (8), then Continue.",
        "If child_age is missing, ask on the terminal and save it.",
        "improve_survey_intelligence() stores question-stem lessons after each verified action.",
    ],
    "24.0.60": [
        "Tap children=1 first. Do not mark it done until the tap executes.",
        "If Continue is off-screen, scroll_down. Never tap y>=88% (Android nav/home).",
        "VLM order: Salad first, then Gemini Flash-Lite, then Flash on failure.",
    ],
    "24.0.59": [
        "After tapping children=1, click Continue. Do not re-tap (that unchecks it).",
        "Leftover red banner is not a failed select. WebView radios rarely report checked.",
        "Tap the UI row for 1, not OCR 1 inside under-18.",
    ],
    "24.0.58": [
        "How-many-children uses knowledge_base number_of_children (1) then Continue.",
        "Single-digit radios 0-9 are real options; typing 2 must not match 10.",
        "Human prompt lists 0-10, writes number_of_children, never a status-bar slug.",
        "Gemini defaults to 3.5-flash-lite / 3.6-flash; 404 retries those names.",
    ],
    "24.0.57": [
        "After Dublin is in the combo, click Continue even if the red banner remains.",
        "Read the selected county from UI nodes and screenshot, not only noisy OCR.",
        "Stagnation asks Gemini a WHO/WHAT/WHY/HOW/WHEN prompt instead of looping open_dropdown.",
    ],
    "24.0.56": [
        "County list: tap Dublin where it is on screen, never a fake y=500 (that hit Laois).",
        "If the open list starts after Dublin (Longford…Wicklow), scroll UP. If it ends before Dublin, scroll down.",
        "List swipes stay inside the dropdown. Continue only after Dublin is the selected value.",
    ],
    "24.0.55": [
        "Command stack: local routers -> Gemini 2.5 Flash-Lite -> one Flash retry -> Salad spare.",
        "Gemini token spend capped at $0.30/hour (survey budget $0.35). Salad 503 never blocks a run.",
        "Unknown screens use Flash-Lite; failed verify or low confidence promotes Flash once.",
    ],
    "24.0.54": [
        "Salad 503/521/522 no longer aborts startup. Local KB/OCR routers fill the survey.",
        "While Salad is down, skip the VLM and keep tapping county/Dublin, Continue, and other known screens.",
    ],
    "24.0.53": [
        "County combo is tapped on the visible value (Donegal), not a phantom Select one.",
        "Dropdown-open verify requires 4+ county names, not any clickable node.",
        "Missed opens retry OCR/chevron offsets, then tap Dublin and Continue.",
    ],
    "24.0.52": [
        "County dropdown uses knowledge_base city=Dublin. Never pick Donegal for Dublin.",
        "Open the list, tap Dublin, then Continue. Salad 521/522 falls back to this local router.",
        "Do not Continue while the field still says Select one.",
    ],
    "24.0.51": [
        "Occupation list is a Select-one, not a matrix. Instruction prose is not an option.",
        "Type 2, option 2, or middle manager → Intermediate managerial; that full label is stored in the KB.",
        "Persona Senior Manager / Lead Data Scientist auto-selects middle manager before Continue.",
    ],
    "24.0.50": [
        "Male/Female radios are tapped in the gray body rows, never at status-bar OCR (y=54).",
        "A tap that leaves the red 'please select an answer' banner is a failed tap, not a selected answer.",
        "Authoritative body coordinates win over a tiny header node for gender.",
    ],
    "24.0.49": [
        "Inspector agent rejects banner/paragraph 'answers' and Continue-on-red-error.",
        "'Are you?' + Male/Female is gender from the KB; Male is tapped before Continue.",
        "Validation banners are not options. required_answer_missing stays true while the red error is visible.",
    ],
    "24.0.48": [
        "Chrome (X/Close Button) is never an answer. Persona/KB runs before inferred guesses.",
        "'Where are you living?' maps to country=Ireland → Republic of Ireland, then Continue.",
        "Close-this-survey confirm always taps GO BACK, never CLOSE SURVEY. Garbage clock OCR keys are not written to the KB.",
        "Next/Continue OCR hits in the header are ignored (y must be below 0.35).",
    ],
    "24.0.47": [
        "Drag-and-drop: swipe the requested tile (e.g. 75) into the dashed box, then Next.",
        "Does not turn a VLM click-75 into scroll_down; HTML5 drag uses input draganddrop/swipe.",
    ],
    "24.0.46": [
        "After the captcha is in the box, tap the Next bar by label/coords. Do not retype or BACK.",
        "Captcha typed-state uses a stable key so OCR noise cannot forget the code.",
    ],
    "24.0.45": [
        "Captcha 'type the following code' is OCR'd/VLM-read, typed into the box, then Next.",
        "That screen is not a matrix; Next is blocked until the code is in the field.",
    ],
    "24.0.44": [
        "After a valid open-text sentence, tap the visible Next bar even if the keyboard is up.",
        "OCR token Next/Continue and full-width blue bars are grounded; keyboard is detected from English (US).",
    ],
    "24.0.43": [
        "Open-text questions type a full sentence of at least N words (role-model box), then submit.",
        "The 5-word hint is not a filled radio; junk like WLeadership/5555 is replaced, not appended.",
    ],
    "24.0.42": [
        "Rank cards are any wide gray bar: Gold, Silver, Bronze, Platinum, Diamond, Emerald*.",
        "Local ranking still runs when Salad returns 521/522 so the agent does not stall.",
    ],
    "24.0.41": [
        "Likert required names come from THIS page (Signature/Premier/Emerald), not a hardcoded Select list.",
        "Unrated visible sliders are tapped; the agent no longer scrolls forever hunting Emerald Select.",
    ],
    "24.0.40": [
        "Rank labels must contain Emerald and be at least 6 characters. Junk 'e' / Mid-Tier is ignored.",
        "The remaining gray bar (Emerald Signature) is tapped, not OCR fragments.",
    ],
    "24.0.39": [
        "Rank cards include Emerald Signature (any gray Emerald* bar), not only Select/Premier.",
        "Continue is blocked until at least 3 items are teal; gray bars are tapped first.",
    ],
    "24.0.38": [
        "Likert ignores off-screen/zero-y nodes so it no longer taps [16,0] in the status bar.",
        "Already-rated teal knobs are skipped; unrated scales are found by scrolling down/up/left/right.",
        "Failed Likert taps recover by scrolling, not by hunting Continue.",
    ],
    "24.0.37": [
        "Likert runs before sticky matrix. 'each of the following' no longer hijacks like/dislike scales.",
        "Navigation Continue is vetoed while Emerald Premier still has the up-arrow handle.",
        "Taps the scale DOT left of 3/4/5, not only the number label.",
    ],
    "24.0.36": [
        "Never Continue a like/dislike page until Emerald Select, Emerald, and Emerald Premier are all tapped.",
        "A teal up-arrow handle at the bottom of a scale is unanswered; WH prompt tells the LLM to tap 3/4/5 first.",
        "teal_radio_filled no longer lets Continue skip the last unrated scale.",
    ],
    "24.0.35": [
        "Likert/slider rating pages tap 3 then 4 then 5 on each named scale and only then Continue.",
        "Does not treat yellow/gray like-dislike dots as a matrix, and does not need the VLM (Salad 503 is skipped).",
    ],
    "24.0.34": [
        "Membership-tier ranking always uses Emerald / Emerald Select / Emerald Premier when those names are on screen.",
        "Rank progress is keyed as membership_tier_rank so the clock/progress OCR cannot reset it.",
    ],
    "24.0.33": [
        "Ranking items are only the wide gray/teal cards (Emerald, Select, Premier), never progress-bar or chrome text.",
        "Already-teal ranked cards are skipped; remaining gray cards are tapped, then Continue.",
        "Failed rank taps do not recover by scrolling the info-page router.",
    ],
    "24.0.32": [
        "Detects click-or-drag ranking screens and does not Continue until every item is placed.",
        "Ranks membership tiers Base→Top as Emerald, Emerald Select, Emerald Premier by tapping each bar once.",
        "Validation Please rate at least 3 items keeps the ranking router in control instead of a landing Continue click.",
    ],
    "24.0.31": [
        "Ignores dump-only Continue nodes that are not in screenshot OCR or the visible band; scrolls instead.",
        "After a failed Continue click on an info page, scrolls down/up/left/right until a real CTA appears.",
        "Off-screen WebView Continue (y below the fold) no longer blocks scrolling.",
    ],
    "24.0.30": [
        "Qualified/info pages with no on-screen CTA scroll until Continue/Next is visible instead of halting.",
        "Low-confidence VLM Continue on navigation/landing becomes a bounded scroll, not request_human.",
        "You have qualified for this survey is enough to classify a landing even when the button is below the fold.",
    ],
    "24.0.29": [
        "After a Select-one radio is filled, click Continue; do not re-tap (that unchecks it).",
        "A leftover red Please-select banner is not treated as unanswered once a teal radio or this-cycle tap exists.",
        "Stabilizes last-select memory on the question text so OCR noise (| am vs I am) cannot retrigger the option.",
    ],
    "24.0.28": [
        "Never tap the Android home/nav bar (y>~90%); that tap minimized the survey.",
        "Prefers the full option I am very open to joining loyalty programs over the OCR fragment very open.",
        "If the launcher/home screen appears, relaunches topsurveys so the survey stays in front.",
    ],
    "24.0.27": [
        "Clears pending Continue when the question changes so employment does not skip loyalty unanswered.",
        "Never Continue while a Select-one radio is empty or a red Please-select-an-answer banner is visible.",
        "Infers I am very open to joining loyalty programs from the early-adopter persona and writes it to the KB.",
        "Maps ungrounded VLM ids such as ans351.0.1 onto the visible option named in answer_reason.",
        "Sends the first VLM attempt at 1152px so Qwen 4096-token context is not exceeded.",
    ],
    "24.0.26": [
        "Releases the matrix session on Select-one questions so employment is not scrolled as a leftover grid.",
        "Fuzzy-matches knowledge_base.json and persona facts onto visible options (Employed Full-Time -> Employed full-time).",
        "Matrix visibility requires a 4-column semantic/visual grid, not a vertical list of radios.",
    ],
    "24.0.25": [
        "Never skip short matrix labels such as Taxi (the 8-char filter left that row empty).",
        "Detect teal filled radios and skip them; do not re-tap a selected circle (that unchecks it).",
        "Do not click Continue while any visible row is empty; scroll to find remaining empty rows.",
        "On a validation-error banner, keep the matrix session and fill empty rows instead of restarting at Personal car.",
    ],
    "24.0.24": [
        "Taps visual radio-circle coordinates; never remaps a matrix cell to a Yes/No text node at (0,0).",
        "Locks the four recency columns so Personal car maps to last-12-months, not the short word No.",
        "Skips unlabeled header rows and does not OCR the screenshot once per row (that cost ~20s).",
        "Treats a successful matrix tap as filling the row even when phash does not change.",
        "Stops calling the matrix router twice per cycle.",
    ],
    "24.0.23": [
        "Detects the 4-column empty-radio matrix from the screenshot when WebView cells are not checkable.",
        "Keeps a sticky matrix session across scrolls so Rentals rows stay in survey_question after the intro scrolls away.",
        "Never lets primary_transport/multi-KB steal a recency grid.",
        "Picks each row from persona/KB (public-transit Dublin family): recent vs never vs 1-3 years.",
        "Scrolls up to 8 times until Continue is grounded, filling newly revealed rows.",
        "Does not convert a truncated VLM JSON (confidence 0) into request_human on a matrix.",
    ],
    "24.0.22": [
        "Treats Select-one-for-each matrix grids as survey_question, not navigation.",
        "Fills one matrix row per cycle with a reasonable default (never-used vs last-12-months) without waiting on the VLM.",
        "Grounds WebView radio circles from the clickable grid when checkable=false.",
        "Scrolls to remaining rows, then clicks Continue once every visible row is answered.",
        "Salvages truncated LLM JSON so a cut-off response cannot stall the run.",
        "Raises the LLM token cap so matrix answers are less likely to be truncated.",
    ],
    "24.0.21": [
        "Grounds the empty age text box (rounded left field under Enter a number) instead of tapping the question title.",
        "Work-habit: KB value -> locate field -> type input_payload -> Continue, matching the D22 postcode flow.",
        "Prefers an empty clickable body node, then the visible rounded input, then OCR below the instruction.",
        "Retries alternate field coordinates on stagnation instead of repeating the same miss.",
        "Double-taps WebView fields to focus before typing.",
        "Adds an age-empty-field screenshot fixture so the tap must land inside the box.",
    ],
    "24.0.20": [
        "Routes What is your age? from knowledge_base.json:age (44) as type_text instead of calling the VLM.",
        "Repairs LLM type_text when the value is in target_text and input_payload is null.",
        "Accepts 4-number bounding boxes as tap coordinates by using the box center.",
        "Taps the empty age field from OCR (below Enter a number), not a too-low underline fallback.",
        "If a personal text/choice question has no KB value, prompts the terminal, saves the answer, and continues.",
        "Non-personal questions still go to the VLM so the survey can proceed.",
    ],
    "24.0.19": [
        "Never re-taps a just-selected radio/checkbox; a second tap was unchecking Male and stalling.",
        "After a stored KB answer is issued, the next cycle clicks Continue/Next instead of selecting again.",
        "Grounds Continue » / Next even when chevrons are present and the button sits mid-screen, not in the nav bar.",
        "Vetoes Privacy Policy, Accessibility Statement, Help and Back as fake progression controls.",
        "Scrolls down once when a completed question has no visible Continue/Next, then grounds the CTA.",
        "Prefers the smallest matching option node and taps the radio to the left of the label.",
        "Records option progress on a successful tap, not only after a green-band/hash postcondition.",
        "Adds a gender-screen regression fixture matching the supplied Continue » layout.",
    ],
    "24.0.18": [
        "Vendors human-answer matching inside survey_with_salad.py so a single-file copy no longer crashes at import.",
        "human_answer_matching.py remains optional: used when present, otherwise the in-file helpers run unchanged.",
        "Keeps the v24.0.17 terminal key-in, KB write, multi-select tick, and pets-household regression behavior.",
    ],
    "24.0.17": [
        "Stops exiting when the VLM is silent or returns request_human on a personal survey question.",
        "Prompts on the terminal for operator key-in (Cat, Dog, Fish / only Fish / none / skip).",
        "Writes the grounded answer into knowledge_base.json, including personal_question_fallbacks.",
        "Re-checks the current screen and ticks every matching visible option before continuing.",
        "Reuses stored multi-select answers on later cycles and later runs without re-prompting.",
        "Adds a pets-household regression fixture matching the supplied qualified checkbox screen.",
    ],
    "24.0.16": [
        "Gives visibly qualified survey landing pages precedence over stale dashboard accessibility nodes left behind by the catalog WebView.",
        "Recognizes qualified/get-started/duration landing language without depending on one exact provider layout.",
        "Grounds Participate and equivalent landing CTAs from current screenshot OCR before considering UIAutomator nodes.",
        "Adds a guarded bottom-button coordinate fallback when the landing page is certain but the WebView hides the CTA label.",
        "Adds a stale-node regression fixture matching the supplied qualified screen and requires a deterministic Participate click.",
    ],
    "24.0.15": [
        "Recognizes the dedicated Surveys catalog from Best Match, Short Surveys and Highest Payout tabs even when OCR entirely misses Cashout.",
        "Classifies repeated duration/payout card grids plus the selected Surveys bottom tab as deterministic navigation rather than a survey question.",
        "Parses survey cards only below the catalog tab strip so balance/progress payouts can never become survey-card targets.",
        "Uses sparse OCR first for two-column catalogs so left and right cards are not merged into a tap in the center gap.",
        "Adds a regression fixture from the failing €0.16 catalog screen and requires the repaired action to land inside a parsed card.",
        "Logs the independent dashboard evidence markers used for each catalog classification and repair.",
    ],
    "24.0.14": [
        "Fixes the observed home-screen failure where OCR missed the exact Featured Surveys header and classified dashboard chrome as a survey question.",
        "Recognizes the dashboard from redundant visible evidence including Balance/Cashout, game tabs, bottom navigation and repeated duration/payout cards.",
        "Runs a sparse-layout OCR recovery pass before allowing an ambiguous survey-question classification to reach the LLM.",
        "Makes recovered dashboard routing deterministic and vetoes model attempts to answer or click Balance, Cashout, payout and bottom-navigation chrome as survey responses.",
        "Adds a regression fixture matching the failing screen and verifies that a hallucinated Balance answer is repaired into a Featured Survey card click.",
        "Records postcondition verification and the observed post-action phase in automation_log.csv instead of reporting an issued tap as a confirmed screen change.",
    ],
    "24.0.13": [
        "Adds horizontal scrolling plus normalized swipe and drag actions for carousels, ranking and reorder controls.",
        "Adds slider positioning, matrix-cell selection, multi-select completion guards and multiline comment entry.",
        "Adds picker-aware date/time entry while retaining one verified atomic action per cycle.",
        "Adds configurable Android permission-dialog routing with sensitive permissions denied unless explicitly enabled.",
        "Adds authorized document-picker selection without inventing or uploading an unconfigured file.",
        "Extends learned screen records with verified transition signatures for reusable multi-step workflows.",
        "Adds advanced-control regression checks while retaining every v24.0.12 navigation and KB-answer safeguard.",
    ],
    "24.0.12": [
        "Classifies postcode and other visible text-entry forms as survey questions even when WebView exposes editable=0.",
        "Routes the Irish routing key D22 from knowledge_base.json:area_code instead of copying the A96 example placeholder.",
        "Finds visually rendered WebView text fields and progression buttons with device-relative image geometry.",
        "Learns only post-action-verified screen actions and reuses them above a configurable confidence threshold.",
        "Penalizes failed learned-action replays so changed layouts automatically fall back to fresh LLM reasoning.",
        "Makes parsed dashboard-card coordinates authoritative instead of OCR-grounding a synthetic tile label elsewhere.",
    ],
    "24.0.11": [
        "Detects cookie-consent overlays before classifying or answering the covered survey question.",
        "Accepts or rejects cookies through a configurable, OCR-grounded one-action overlay handler.",
        "Stops treating the word participate inside a question as a survey-landing Participate button.",
        "Records the user-declared webcam-interview willingness preference and reuses it through the knowledge base.",
        "Carries a verified single-choice selection into a separate grounded Continue/Next action on the following cycle.",
        "Adds regression checks for cookie overlays and questions whose wording contains participate.",
    ],
    "24.0.10": [
        "Rejects blank or mismatched accessibility nodes when the LLM supplies visible target text, preventing wrong-row taps.",
        "Routes exact scalar KB facts such as smoking_status directly to the matching visible option before model inference.",
        "Gives visible disqualification overlays precedence over stale dashboard nodes exposed underneath the modal.",
        "Grounds and clicks prominent Okay/OK/Done terminal buttons before falling back to the top-left Close/X control.",
        "Resets debug log, action log, screenshots and agent state at the start of every fresh run.",
    ],
    "24.0.9": [
        "Classifies closed, unavailable, quota-full and ineligible survey pages as terminal modals requiring exit.",
        "Preserves the LLM's close instruction after validating it against a grounded top-left Close/X control.",
        "Repairs malformed close-button bounds into a current-screen node or safe normalized top-left coordinate.",
        "Allows a validated non-destructive modal-close action through the confidence gate even when the model emits confidence zero.",
        "Skips the just-closed Featured Survey card when routing back to the dashboard.",
    ],
    "24.0.8": [
        "Recognizes a visibly selected answer even when WebView accessibility does not expose checked/selected state.",
        "Routes a completed question to its bottom Next/forward control instead of selecting the same answer repeatedly.",
        "Grounds unlabeled bottom-center arrow buttons from current device-relative UI geometry with a guarded visual fallback.",
        "Verifies answer selection from accessibility state, selected-color evidence, or a changed screen hash.",
        "Keeps verification screenshots available until visual postcondition checks finish.",
    ],
    "24.0.7": [
        "Keeps the stable filename survey_with_salad.py while recording releases inside the file and runtime state.",
        "Routes configured personal-question answers before invoking the multimodal model.",
        "Recognizes Salad decoder-prompt/max_model_len errors and performs one compact visual retry.",
        "Reduces primary and retry image dimensions to leave reliable room inside Qwen's 4096-token context.",
        "Compacts persona and knowledge-base evidence while retaining broad coverage for unfamiliar survey questions.",
    ],
    "24.0.6": [
        "Adds phase-aware routing so dashboard/navigation screens never receive persona or answer-memory context.",
        "Restores structured Featured Survey tile discovery and deterministic survey-card selection.",
        "Validates and repairs LLM actions against the current screen phase before execution.",
        "Adds OCR text-coordinate grounding when WebView controls are missing from UIAutomator.",
        "Deduplicates perceptually identical screenshots instead of saving one file per failed cycle.",
        "Replaces warning-only stagnation with bounded alternate-target recovery and a hard stop.",
        "Uses dynamic device-relative scroll coordinates instead of fixed 1080x2400-era values.",
    ],
    "24.0.5": [
        "Loads the structured MASTER_USER_PERSONA from persona_data.py and supplies it to the decision model.",
        "Adds a declared/verified/inferred evidence hierarchy for ordinary personal and lifestyle questions.",
        "Allows user-authorized reasonable inference when an exact non-sensitive personal fact is absent.",
        "Persists inferred answers with question, confidence, source basis, and timestamp for consistent reuse.",
        "Adds data-driven personal_question_fallbacks so known questions can recover from request_human decisions.",
        "Clarifies that underlined 'I can't answer' text is a link, not evidence that it is selected.",
    ],
    "24.0.4": [
        "Compressed UI evidence by prioritizing actionable nodes and limiting text-only nodes.",
        "Compacted the system/observation prompts and JSON to fit Qwen's 4096-token context window.",
        "Capped the primary vision long edge at 1536px and the action response budget at 500 tokens.",
        "Added one automatic ultra-compact retry at 1280px/400 output tokens for context-length HTTP 400 errors.",
        "Replaced deprecated datetime.utcnow() with timezone-aware UTC timestamps.",
        "Retained v24.0.3 organization validation, S4 authorization preflight, and foreground-app fallbacks.",
    ],
    "24.0.3": [
        "Rejects placeholder or invalid SALAD_ORGANIZATION values before the first screenshot.",
        "Adds S4 authorization preflight using GET /organizations/{organization}/files.",
        "Logs an explicit distinction between Qwen vision success and S4 storage authorization.",
        "Improves foreground-app detection with activity/window fallbacks.",
        "Prevents the v24.0.2 failure where YOUR_SALAD_ORGANIZATION_SLUG passed the non-empty check.",
    ],
    "24.0.2": [
        "Fixed Salad vision transport: local screenshots are uploaded to Salad S4 and passed to Qwen as downloadable HTTPS image URLs.",
        "Kept optional data_url transport for endpoints that explicitly support inline base64 images.",
        "Added exact HTTP error-body logging for LLM and storage failures.",
        "Added fail-fast handling for deterministic 4xx LLM request errors instead of looping up to 200 steps.",
        "Added Salad S4 cleanup after inference so temporary remote screenshots are deleted when configured.",
        "Added multimodal preflight using a public image URL so startup validates vision, not only text chat.",
        "Explicitly supports visual coordinate grounding for WebView fields when UIAutomator exposes editable=0.",
    ],
    "24.0.1": [
        "Fixed ADB device discovery so host-level `adb devices -l` never inherits -s DEVICE_ID.",
        "Made ADB device-state parsing whitespace-safe instead of requiring a literal tab.",
        "Automatically binds DEVICE_ID when exactly one online device is found.",
        "Adds raw ADB discovery output to failure logs for easier troubleshooting.",
    ],
    "24.0.0": [
        "Removed hard-coded postcode execution path.",
        "Removed hard-coded screen resolution.",
        "Added dynamic ADB device/display discovery.",
        "Raised vision image size from 768px to configurable 1800px.",
        "Added UIAutomator-first grounding for editable and clickable nodes.",
        "Added atomic action + postcondition verification loop.",
        "Added explicit observation/state/action schema.",
        "Added dropdown, checkbox/radio, long-press, keyevent and text-entry actions.",
        "Added stale-action prevention using screen-state hashes.",
        "Added knowledge-base provenance and canonical deduplication.",
        "Moved Salad credential requirement to .env.",
        "Added fresh-run cleanup without deleting the persistent knowledge base.",
    ]
}

