# 이미지 프롬프트 규칙

> 적용: `osmu-visual`. 입력은 핵심내용 5가지(03_key_points.md), 페르소나(02_persona.md 3절 하루 일과), 카피(04_copy.md).

## 블로그 이미지 5장 (가로형)

- 핵심내용 **각 1장**, 비율 16:9(1920×1080). `images/blog_1.jpg` ~ `blog_5.jpg`.
- **실사(photorealistic)**. 일러스트·3D·만화 금지.
- **이미지 안에 글자·로고·워터마크·UI 텍스트 없음.** 프롬프트 끝에 항상: `No text, no letters, no numbers, no logos, no watermark, no UI.`
- 장면은 페르소나의 하루 일과(장소·물건·시간대)에서 가져온다. 핵심내용의 "순간"을 보여주는 장면 — 개념 설명 그림이 아니다.
- 사람은 뒷모습·손·실루엣 위주. 얼굴 정면 클로즈업 금지(생성 품질·초상권). 한국 생활 공간의 디테일(아파트 거실, 동네 카페, 지하철, 편의점 등).
- 5장은 조명·색감·시간대가 이어지는 **한 세계관**. 같은 구도 반복 금지(와이드 / 미디엄 / 디테일 섞기).
- 프롬프트는 영어, 60~120단어. 구조: `[피사체·행동] in [장소·시간대], [조명], [카메라·렌즈 느낌], [분위기]. No text…`

## 인스타 배경 1장 (3:4)

- `images/instagram_bg.jpg`, 1080×1440. 블로그 1번 장면의 변주 또는 가장 감정이 강한 핵심내용의 장면.
- 상단 또는 하단 1/3이 **비교적 단순**(하늘·벽·테이블면)해야 카피를 얹을 수 있다. 프롬프트에 `clean negative space at the top third` 같은 지시를 넣는다.
- 글자 합성은 `osmu.py compose` 가 한다(이미지 모델에 글자를 맡기지 않는다).

## 숏츠 장면 (실사 스타일일 때)

- 세로 9:16(1080×1920). script.json 의 beat 별 scene_prompt 를 그대로 쓰되 위 원칙 동일.
- 이미지→영상 클립용 모션 프롬프트는 "subtle camera push-in, stable composition, no new text, preserve subject" 수준의 작은 움직임만.

## 스톡 검색어 (query)

- 모든 항목에 영어 검색어 `query` 를 함께 쓴다. 무료 스톡(Pexels/Pixabay)을 쓰는 설치자는 이것으로 사진을 찾고, 생성 서비스가 실패해도 이것으로 대체한다.
- 화면에 **보이는 것** 2~4단어: 사물 + 장소 + 시간대(`"laptop cafe morning"`, `"subway commuter phone"`). 추상어(success, idea, growth)·한국어·고유명사 금지.
- 5장은 서로 다른 검색어로(같은 사진이 반복되지 않게). 스톡 사진은 한국 공간이 아닐 수 있으니 장소보다 사물 중심이 안전하다.
- 숏츠 장면은 beat 별 `scene_query` 로 같은 규칙.

## 출력

`images/prompts.json`
```json
[{"file": "blog_1.jpg", "key_point": 1, "ratio": "16:9", "prompt": "…", "query": "…"}, …, {"file": "instagram_bg.jpg", "ratio": "3:4", "prompt": "…", "query": "…"}]
```
생성은 `osmu.py image --prompts images/prompts.json` 로 실행한다(서비스는 config `image_provider` — stock | gemini | pixverse). 스톡 사진의 출처는 `images/credits.json` 에 자동 기록된다.

## 검수 포인트

5장 모두 존재 / 가로 비율 / 글자 없음(검수 팀원이 이미지를 직접 봄) / 세계관 일관 / 인스타 배경에 카피 공간
