# Recording script for M5 (speech)

**What this is for.** These recordings measure two things:
- how well speech-to-text hears Kannada and English questions about pesticides;
- whether the whole app still gives the register's answer when the question is spoken.

Each line is tied to a register answer (in `script.jsonl`).

## How to record

1. **A quiet room and your phone's voice recorder.** Any format is fine (m4a, mp3, wav, ogg).
2. **One file per line, named by the line's ID:** `KN-01.m4a`, `KN-02.m4a`, … `FU-05b.m4a`.
3. **Say the line once, at normal speed,** the way you would ask at a shop counter. Say product names as you would read the label; English is fine. Say "%" and numbers however you naturally do.
4. **If a line sounds unnatural in Kannada, change the wording before you record it,** keeping the meaning, and write what you actually said in the third column. The word error rate is then measured against what you said.
5. **The FU lines are short conversations.** Record FU-01a, then FU-01b ("and for X?"); FU-01b continues FU-01a.
6. **Put the files in** `evaluation/e5/audio/`. That folder is never committed to GitHub.

## Consent and privacy

- These are recordings of **your own voice**. Anyone else's voice needs that person's consent first.
- The audio stays on this computer. It is used only to measure speech-to-text, and you can delete it at any time.
- **One choice for you:** one of the options to test is Groq's hosted Whisper (on your existing key). Testing it **sends the audio to Groq**. The local models (AI4Bharat IndicConformer) keep it on this machine. I will ask before sending any audio anywhere.

## The lines (70: 50 Kannada, 10 English, 5 two-turn conversations)

| ID | Line | What I actually said (only if different) |
|---|---|---|
| KN-01 | ಆಲೂಗಡ್ಡೆಯಲ್ಲಿ late blight ಜಾಸ್ತಿ ಆಗಿದೆ, Copper Hydroxide 53.8% DF ಸರಿ ನಾ? | |
| KN-02 | Cyazofamid 34.5% SC ಹೊಡೆದ ಮೇಲೆ ಆಲೂಗಡ್ಡೆ ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು? | |
| KN-03 | Captan 75% WP ಆಲೂಗಡ್ಡೆಗೆ ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ? | |
| KN-04 | Oxathiapiprolin 4.61% w/w + Amisulbrom 23.08% w/w SE ಹೊಡೆದ ಮೇಲೆ ದ್ರಾಕ್ಷಿ ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು? | |
| KN-05 | ಮೆಕ್ಕೆಜೋಳಕ್ಕೆ shoot fly ಬಂದಿದೆ, Thiamethoxam 30% WS ಹೊಡೆಯಬಹುದಾ? | |
| KN-06 | ಶೇಂಗಾಕ್ಕೆ Propiconazole 25% EC ಎಷ್ಟು ಹಾಕಬೇಕು? | |
| KN-07 | ಎಲೆಕೋಸಿಗೆ diamond back moth ಬಂದಿದೆ, Flometoquin 10% SC ಹೊಡೆಯಬಹುದಾ? | |
| KN-08 | Flubendiamide 39.35% w/w SC ಅನ್ನು ಏಲಕ್ಕಿಯಲ್ಲಿ capsule borer ಗೆ ಬಳಸಬಹುದಾ? | |
| KN-09 | ಕಡಲೆಗೆ pod borer ಬಂದಿದೆ, CHLORANTRANILIPROLE 5.2% + NOVALURON 8.5% SC ಹೊಡೆಯಬಹುದಾ? | |
| KN-10 | Carboxin 75% WP ಅನ್ನು ಗೋಧಿಯಲ್ಲಿ loose smut ಗೆ ಬಳಸಬಹುದಾ? | |
| KN-11 | ಎಲೆಕೋಸಿಗೆ Malathion 50.00% EC ಎಷ್ಟು ಹಾಕಬೇಕು? | |
| KN-12 | ಆಲೂಗಡ್ಡೆಗೆ Metalaxy l8% + Mancozeb 64% WP ಎಷ್ಟು ಹಾಕಬೇಕು? | |
| KN-13 | Lambda-cyhalothrin 05% EC ಹೊಡೆದ ಮೇಲೆ ಈರುಳ್ಳಿ ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು? | |
| KN-14 | Quinalphos 25% EC ಅನ್ನು ಹೂಕೋಸಿನಲ್ಲಿ stem borer ಗೆ ಬಳಸಬಹುದಾ? | |
| KN-15 | Metiram 55% + Pyraclostrobin 5% WG ಹೊಡೆದ ಮೇಲೆ ಹೆಸರು ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು? | |
| KN-16 | Beta-cyfluthrin 08.49% + Imidacloprid 19.81% w/w OD ಹೊಡೆದ ಮೇಲೆ ಸೌತೆಕಾಯಿ ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು? | |
| KN-17 | ಭತ್ತಕ್ಕೆ sheath blight ಬಂದಿದೆ, Azoxystrobin 7.1% + Propiconazole 11.9% w/w SE ಹೊಡೆಯಬಹುದಾ? | |
| KN-18 | Beta-cyfluthrin 08.49% + Imidacloprid 19.81% w/w OD ಸೌತೆಕಾಯಿಗೆ ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ? | |
| KN-19 | ಮೆಣಸಿನಕಾಯಿಗೆ Pyraclostrobin 20% WG ಎಷ್ಟು ಹಾಕಬೇಕು? | |
| KN-20 | Imidacloprid 48% FS ಜೋಳಕ್ಕೆ ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ? | |
| KN-21 | ತೊಗರಿಯಲ್ಲಿ ಕಾಯಿ ಕೊರಕ ಜಾಸ್ತಿ ಆಗಿದೆ, Emamectin benzoate 05% SG ಸರಿ ನಾ? | |
| KN-22 | ಸೌತೆಕಾಯಿಗೆ downey mildew ಬಂದಿದೆ, Ametoctradin 27% + Dimethomorph 20.27% w/w SC ಹೊಡೆಯಬಹುದಾ? | |
| KN-23 | Emamectin benzoate 01.90% EC ಕಡಲೆಗೆ ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ? | |
| KN-24 | Chlorantraniliprole 18.50% SC ಹೊಡೆದ ಮೇಲೆ ಬೆಂಡೆಕಾಯಿ ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು? | |
| KN-25 | ಉದ್ದಿನಲ್ಲಿ bihar hairy caterpillar ಜಾಸ್ತಿ ಆಗಿದೆ, Quinalphos 25% EC ಸರಿ ನಾ? | |
| KN-26 | ಈರುಳ್ಳಿಗೆ purple blotch ಬಂದಿದೆ, Difenoconazole 25% EC ಹೊಡೆಯಬಹುದಾ? | |
| KN-27 | ತೊಗರಿಗೆ pod borer ಬಂದಿದೆ, Spinosad 45% SC ಹೊಡೆಯಬಹುದಾ? | |
| KN-28 | ದ್ರಾಕ್ಷಿಗೆ Fenamidone10% + Mancozeb50% WG ಎಷ್ಟು ಹಾಕಬೇಕು? | |
| KN-29 | ತೊಗರಿಗೆ ಕಾಯಿ ಕೊರಕ ಬಂದಿದೆ, Spinosad 45% SC ಹೊಡೆಯಬಹುದಾ? | |
| KN-30 | Mancozeb 40% + Tebuconazole 1% WS ಶೇಂಗಾಕ್ಕೆ ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ? | |
| KN-31 | Kitazin 48% EC ಅನ್ನು ಆಲೂಗಡ್ಡೆಯಲ್ಲಿ early blight ಗೆ ಬಳಸಬಹುದಾ? | |
| KN-32 | ಭತ್ತಕ್ಕೆ leaf folder ಬಂದಿದೆ, Deltamethrin 11% w/w EC ಹೊಡೆಯಬಹುದಾ? | |
| KN-33 | ಉದ್ದಿಗೆ cercospora leaf spot ಬಂದಿದೆ, Metiram 70% WG ಹೊಡೆಯಬಹುದಾ? | |
| KN-34 | ಬದನೆಕಾಯಿಯಲ್ಲಿ jassids ಜಾಸ್ತಿ ಆಗಿದೆ, Dimethoate 30% EC ಸರಿ ನಾ? | |
| KN-35 | Pyriproxyfen 10% + Bifenthrin10% w/w EC ಅನ್ನು ಹೆಸರಿನಲ್ಲಿ ಬಿಳಿ ನೊಣ ಗೆ ಬಳಸಬಹುದಾ? | |
| KN-36 | Flometoquin 10% SC ಮೆಣಸಿನಕಾಯಿಗೆ ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ? | |
| KN-37 | ಮಾವಿನಲ್ಲಿ mango hoppers ಜಾಸ್ತಿ ಆಗಿದೆ, Flonicamid 50% WG ಸರಿ ನಾ? | |
| KN-38 | Fluensulfone 2% GR ಅನ್ನು ಬೆಂಡೆಕಾಯಿಯಲ್ಲಿ root knot nematode ಗೆ ಬಳಸಬಹುದಾ? | |
| KN-39 | ಆಲೂಗಡ್ಡೆಗೆ Azoxystrobin 13.04% + Thifluzamide 15.66% w/w SC ಎಷ್ಟು ಹಾಕಬೇಕು? | |
| KN-40 | ಹೂಕೋಸಿನಲ್ಲಿ ಕಾಂಡ ಕೊರಕ ಜಾಸ್ತಿ ಆಗಿದೆ, Quinalphos 25% EC ಸರಿ ನಾ? | |
| KN-41 | ಜೋಳಕ್ಕೆ downey mildew ಬಂದಿದೆ, Metalaxyl-M 31.8% ES ಹೊಡೆಯಬಹುದಾ? | |
| KN-42 | ಹತ್ತಿಯಲ್ಲಿ spotted boll worm ಜಾಸ್ತಿ ಆಗಿದೆ, Spinetoram 11.70% SC ಸರಿ ನಾ? | |
| KN-43 | Chlorantraniliprole 10% w/w + Novaluron 20% w/w SC ಮೆಕ್ಕೆಜೋಳಕ್ಕೆ ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ? | |
| KN-44 | Quinalphos 25% EC ಅನ್ನು ದಾಳಿಂಬೆಯಲ್ಲಿ scales ಗೆ ಬಳಸಬಹುದಾ? | |
| KN-45 | Methoxyfenozide 21.8% w/w SC ಅನ್ನು ಶೇಂಗಾದಲ್ಲಿ leaf eating caterpillar ಗೆ ಬಳಸಬಹುದಾ? | |
| KN-46 | ತೆಂಗಿನಲ್ಲಿ eriophyid mites ಜಾಸ್ತಿ ಆಗಿದೆ, Fenpyroximate 05% EC ಸರಿ ನಾ? | |
| KN-47 | Lufenuron 05.40% EC ಹೊಡೆದ ಮೇಲೆ ಹೂಕೋಸು ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು? | |
| KN-48 | ಟೊಮೆಟೊಗೆ red spider mites ಬಂದಿದೆ, Tebufenpyrad 20% WP ಹೊಡೆಯಬಹುದಾ? | |
| KN-49 | Fluensulfone 2% GR ಹೊಡೆದ ಮೇಲೆ ದಾಳಿಂಬೆ ಎಷ್ಟು ದಿನಕ್ಕೆ ಕೊಯ್ಲು ಮಾಡಬಹುದು? | |
| KN-50 | Triticonazole 80 g/l + Pyraclostrobin 40 g/l FS ಗೋಧಿಗೆ ರಿಜಿಸ್ಟರ್ ಆಗಿದೆಯಾ? | |
| EN-01 | Can I spray Fenpyroximate 05% EC on coconut for eriophyid mites? | |
| EN-02 | How many days after spraying Ethion 50% EC can I harvest cotton? | |
| EN-03 | Is Fenpyroximate 05% SC registered for yellow mite in chilli? | |
| EN-04 | Can I spray Triadimefon 25% WP on wheat for powdery mildew? | |
| EN-05 | How many days after spraying Thiamethoxam 30% FS can I harvest groundnut? | |
| EN-06 | Is Flubendiamide 39.35% w/w SC registered for capsule borer in cardamom? | |
| EN-07 | Can I spray Dimethoate 30% EC on bhindi for aphid? | |
| EN-08 | How many days after spraying Profenofos 50% EC can I harvest onion? | |
| EN-09 | Is Carbofuran 03% CG registered for stem borer in jowar? | |
| EN-10 | Can I spray Difenoconazole 25% EC on pomegranate for fruit rot? | |
| FU-01a | ಜೋಳಕ್ಕೆ shoot fly ಬಂದಿದೆ, Carbofuran 03% CG ಹೊಡೆಯಬಹುದಾ? | |
| FU-01b | ಮತ್ತೆ ಗೋಧಿಗೆ? | |
| FU-02a | ಬದನೆಕಾಯಿಗೆ ಬಿಳಿ ನೊಣ ಬಂದಿದೆ, DIMPROPYRIDAZ 120 g/l SL ಹೊಡೆಯಬಹುದಾ? | |
| FU-02b | ಮತ್ತೆ ಬೆಂಡೆಕಾಯಿಗೆ? | |
| FU-03a | ಬೆಂಡೆಕಾಯಿಗೆ ಕಾಯಿ ಕೊರಕ ಬಂದಿದೆ, Quinalphos 25% EC ಹೊಡೆಯಬಹುದಾ? | |
| FU-03b | ಮತ್ತೆ ಮಾವಿಗೆ? | |
| FU-04a | ಗೋಧಿಗೆ stem rust ಬಂದಿದೆ, Propiconazole 25% EC ಹೊಡೆಯಬಹುದಾ? | |
| FU-04b | ಮತ್ತೆ ಆಲೂಗಡ್ಡೆಗೆ? | |
| FU-05a | ಮೆಕ್ಕೆಜೋಳಕ್ಕೆ spotted stemborer ಬಂದಿದೆ, Chlorantraniliprole 50% W/w FS ಹೊಡೆಯಬಹುದಾ? | |
| FU-05b | ಮತ್ತೆ ಏಲಕ್ಕಿಗೆ? | |
