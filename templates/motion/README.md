# 모션 템플릿 (HTML → 영상)

숏츠의 모션그래픽 장면은 이 폴더의 HTML 파일 하나가 장면 하나입니다. CSS만 알면 새 디자인을 추가할 수 있습니다.
렌더러 `scripts/video/html_render.py` 가 Playwright(Chromium)로 열어 1/30초마다 화면을 찍고 FFmpeg로 영상을 만듭니다.

## 새 템플릿 추가하기

1. 기존 파일(예: `kinetic_full.html`)을 복사해 `my_card.html` 로 저장합니다. 파일 이름이 곧 템플릿 이름입니다(`_` 로 시작하는 파일은 공용 파일).
2. 글자 자리에 `{{이름:text=기본값}}` 을 씁니다. 장면 계획(plan.json)의 `props.이름` 값이 들어갑니다(HTML 이스케이프됨).
   - 타입: `text`(기본) · `number` · `color` · `bool`
   - 목록 같은 복잡한 값은 스크립트에서 `OSMU.props.items` 처럼 읽습니다.
3. 색은 직접 쓰지 말고 `var(--bg)` `var(--accent)` `var(--text)` `var(--muted)` 를 씁니다(브랜드 색이 자동 적용).
4. 크기는 `calc(var(--u) * 숫자)` 로 씁니다. `--u` 는 화면 짧은 변의 1%라서 9:16·1:1·16:9 모두에서 비율이 맞습니다.
5. 확인: `python scripts/osmu.py motion-preview my_card --props '{"title":"테스트"}'` → `output/motion-preview/my_card.png` 와 `.mp4`.

## 지켜야 할 약속 (영상이 매번 똑같이 나오도록)

- 움직임은 **CSS 애니메이션/트랜지션**으로만 만듭니다. 렌더러가 프레임마다 모든 애니메이션의 시점을 고정합니다.
- `Date.now()`, `setTimeout`, `requestAnimationFrame`, `Math.random()` 으로 움직임을 만들지 않습니다(찍을 때마다 달라짐).
- 무한 반복(`infinite`) 애니메이션은 쓰지 않습니다.
- 인터넷에서 글꼴·이미지를 불러오지 않습니다(무인 실행·오프라인에서 깨짐). 글꼴은 `_base.css` 의 Pretendard 를 씁니다.
- 등장 효과는 `class="enter"` + `style="--d: 0.3s"`(지연)로 공용 효과를 쓸 수 있습니다.

## 렌더러가 넣어 주는 것

- `:root` 변수: `--bg --accent --text --muted`(브랜드 색), `--dur`(장면 길이), `--u`
- `window.OSMU = {props, colors, duration, width, height}`
- 다음 장면과 컷으로 이어지면 `body.fade-out`(끝 0.27초 페이드)

Playwright가 없으면 같은 이름의 정적 카드(Pillow)로 대체되고, `motion_engine: remotion` 으로 바꾸면 기존 Remotion 렌더를 씁니다.
