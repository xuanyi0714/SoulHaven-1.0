# 前端图片

图片统一从 `/static/pictures/` 读取；旧 `picture` 目录和地址已移除。角色形象另存于角色目录。欢迎插画是页面装饰，不是角色资料或世界观配置。

## characters.png / archive_room.png / archive_trees.png

characters.png 保留为原始书馆图与加载失败回退。内置 imagegen 生成两张 1672×941 静态分层素材：archive_room.png 是移除植物并补齐窗框后的静态底图，archive_trees.png 是带真实 alpha 的四棵植物图层。生成后已查看并检查透明通道；通过前端裁取各植物、调整回场景位置，保持花瓶固定，只让透明树冠错相摆动。右侧较高花瓶现由手写 archive_pedestal.svg 花台承托，详见下文；花台与背景共用坐标和 cover 对齐，不参与摆动。窗框不进入活动图层，光效由另一 Canvas 绘制。没有生成视频，也没有消耗 Runway 额度。实现见 web/js/archive/background.js。

静态补景的完整提示词（参考 characters.png，内置 imagegen）：
```text
Use case precise-object-edit. Create a CLEAN BACKGROUND PLATE for a layered animation of this exact lavender glass library. Remove ALL FOUR ornamental leafy plants/trees and their vases (far left cropped vase on table, small plant at x24% y50%, small plant at x67% y50%, taller plant at x76% y40%). Reconstruct the stationary straight window mullions, glass, wall and floor behind them. Keep the entire exact wide 16:9 composition, camera, architecture, bookshelves, furnishings, original pale lavender colors, soft illumination, sparkles. Do not move or redesign any windows or shelving. NO plants or leaves left anywhere. No new objects, no text. Same full-frame scene, not a collage. This background must stay completely still while separately extracted transparent plants sway in front.
```

透明树层的完整提示词（参考 characters.png，内置 imagegen，transparent_background=true）：
```text
Use case background-extraction. Extract ONLY the FOUR existing ornamental plants with ALL their delicate leaves, branches, stems and vases from this exact reference into a genuinely TRANSPARENT RGBA image. Preserve their exact original full-frame positions and sizes on the same wide 16:9 canvas. Far-left plant cropped by frame x0-8% y18-60%; small left plant x21-28% y37-67%; small right plant x63-71% y35-67%; right-back plant x73-79% y30-53%. Preserve the original very pale lavender-blue stylized illustration and original plant/vase shapes. Every window, window mullion, floor, bookshelf, wall, table and light sparkle must be removed, including all gaps BETWEEN branches and leaves, which must be fully transparent. Do NOT include any rectangular patch of background or any architectural line. Keep all four plants separated at original scene coordinates, do not center or enlarge them, do not crop the canvas to their bounds. The output is an overlay asset for the original scene, no text, no shadow background, no checkerboard pattern baked in.
```

## archive_pedestal.svg

手写的静态矢量花台，用来承托书馆右侧原本悬空的花瓶。画布与书馆分层图同为 1672×941，浅紫白色石材、细凹槽和柔和接触阴影；台面位于场景坐标 (1278.5, 525)，底座落在约 y=653 的地面。台面接住现有花瓶足部，不移动或重绘花瓶、树冠、窗框和书架。

由独立 img 图层显示在植物 Canvas 后面，object-fit: cover / center top 与背景和植物坐标一致。只有树层、书馆和花台都成功加载才显示分层场景；花台加载失败时回退完整 characters.png。SVG 不做循环动画，树冠风动、独立光效及减少动态支持沿用。此素材为代码绘制，没有调用图像生成工具。

## seaside_tea.webp / seaside_tea_mobile.webp

当前聊天试玩欢迎背景。以原版 `seaside_friends.png` 为底，用内置 imagegen 重绘三位旅人的五官、手部和闭嘴表情，并提高蓝天、海水和花丛的饱和度。横版 1671×941，窄屏版 1122×1402。欢迎页按视口预加载并解码对应插画。桌面仅在深蓝文案后局部提亮，窄屏保留三位人物并将文案下移。

横版重绘提示词：

```text
Use case precise-object-edit. Edit this exact original 16:9 SoulHaven Mediterranean garden tea terrace illustration. Preserve the composition, camera, size and exact placement of the three women, outfits and hair color identities (silver lavender, salmon pink, soft blue), teacups, sketchbook, floral terrace, table, right-hand blue door, cat, train bridges, distant town, sunny lake and generous left-side scenery for HTML text. Redraw the faces and hands with the care of a high-end 2D anime movie keyframe: clean expressive eye shapes, naturally aligned eyes in profile, fine graceful features, tidy delicate facial and hair linework, and believable hands. These are three elegant friends in a quiet, natural moment. IMPORTANT facial expressions, make them distinct: silver-haired woman has CLOSED lips with a tiny content smile, listening to pink-haired friend; pink-haired woman has a small CLOSED-lip amused smile with lively eyes, holding the cup comfortably at her chest; blue-haired woman has a CLOSED mouth and thoughtful soft eyes, looking back toward the others. Draw all three mouths CLOSED, indicated by a simple delicate closed lip line, no visible teeth, no open gaps or shouting faces. Keep the framing wide and the three figures at the same visual scale. Increase the original environment’s saturation and sunny contrast in a selective tasteful way: clearer rich azure sky, sparkling vivid cyan and turquoise water, warm cream sun on stone, colorful coral roses and violet wisteria, stronger olive green foliage. Keep skin soft and naturally colored and clouds luminous white. Left stays uncluttered. Preserve original painterly environmental details, camera and placement as closely as possible. Edge-to-edge illustration, no text, no UI, no fourth person, no sticker or chibi, no logo.
```

窄屏重构提示词：

```text
Use case responsive portrait recomposition. Create a 4:5 portrait background asset for the mobile edition of the exact provided revised Mediterranean seaside garden tea terrace illustration. Preserve the same original three anime women with silver, salmon pink, and soft blue hair, same lavender, peach, and blue dresses, same closed mouth expressions and identity, group in the midground with all three faces fully visible, heads around y=39–50% and within x=18–83%. Silver-haired friend listens with a closed-lip tiny smile, pink-haired friend looks amused with a closed-lip smile, blue-haired friend looks thoughtful with her lips closed. Absolutely no open mouths, teeth or talking. Show their cups, tea table and sketchbook, purple wisteria overhead, bright white clouds, clear saturated azure sky, vivid turquoise sea, distant hillside villages, and flower-lined sunlit terrace. Keep the upper 17% chiefly scenic so navigation can overlay and the lower 23% mainly terrace stones and decorative flowers. Clean, fine 2D anime facial linework and naturally colored skin. Maintain a loose wide group framing within the portrait, with all three comfortably visible even in narrow layouts. Edge-to-edge illustration, no text, UI, watermark, or sticker.
```

## seaside_clouds.webp

聊天试玩欢迎页此前使用的透明薄云素材。内置 imagegen 生成，缩为 960×320 WebP 并保留透明通道。现行桌面动态背景为 `web/videos/seaside_breeze.mp4`。

```text
Generate a transparent PNG cloud overlay sprite for a bright hand-painted 2D anime seascape, landscape format around 3:1. Only a single loose, shallow bank of bright white sunlit coastal clouds and thinner streaks of cirrus, in an elegant windblown horizontal shape, with soft feathery edges, subtle pale periwinkle and pale cyan cel-painted shading. These are small wispy clouds high in a sunny summer sky, stretched horizontally, with a few delicate separated wisps and fully transparent gaps around them; do not make a large vertical cumulus tower. The cloud mass tapers toward the right, with a somewhat brighter fluffy section around the left-middle. Hand-painted anime landscape background aesthetic, delicate cool blue and warm white lighting. All clouds entirely inside the frame with transparent padding. Absolutely transparent background (real alpha), no colored sky, no horizon, no landscape, no outline, no words, no objects.
```

## seaside_friends.png

前版横屏欢迎背景。白发、粉发、蓝发三位二次元人物的花园茶会，明亮海滨场景。内置 imagegen 生成后，根据笔记本裁切再次调整人物位置，已检查实际页面截图。

初始生成提示词：
```text
Use case: illustration-story. Asset: a bright landscape 16:9 anime background for a welcoming fictional companion world. FINISHED HAND-DRAWN 2D ANIME FILM KEY VISUAL, elegant clean linework, cel-painted faces, watercolor-like environmental detail; not photoreal humans, not 3D, not a doll render. On a flower-lined seaside garden terrace above a picturesque coastal village, THREE distinct anime friends spend a relaxed sunny afternoon together. One has flowing SILVER-WHITE hair and a lavender ribbon, wears a modest pale lavender day dress; one has a soft PASTEL-PINK bob, a white blouse and peach pinafore skirt; one has SKY-BLUE hair in a loose ponytail, a navy bow and a pale blue long-sleeved dress. Cute youthful anime heroine designs, natural expressions, fully clothed casual outfits. They chat, hold tea cups or a small sketchbook, with gentle smiles and believable hands. They are part of a living world, not posing as a beauty advertisement. Wide environmental composition, camera pulled BACK: all three characters in the middle distance, each knee-up or full-body, each only about 30-40% of canvas height; their heads must not be huge. Spread them naturally across the center-right and right side at DIFFERENT DEPTHS around a small terrace table and railing, with equally balanced visual importance. Do not create a single dominant closeup. Use the entire LEFT 40% for a spacious softly lit cream wall, pale blue sea and calm sky where dark page lettering can sit. Clear turquoise bay, little sailboats, a stone railway bridge and pastel hillside houses, distant soft mountains, climbing roses and hanging wisteria. Bright white clouds, soft sunlight, light breeze moving ribbons and hair. Luminous high-key palette: milk white, sea-glass mint, pale azure, pink and lilac accents, warm sunlit stone. Avoid harsh yellow or dark vignette. Leave breathing room and margins around every character so a web background crop can work. No title, typography, logos, UI, collage panels, borders, watermark, desktop icons. A tasteful joyful ensemble scene with a beautiful landscape and no one face hogging the picture.
```

最终构图调整提示词（以上一版横屏图为参考）：
```text
Adjust ONLY composition of this beautiful anime seaside group scene. Keep all three girls, their white/pink/blue hair, clothes, friendly tea interaction, bright 2D anime style, sea, bridge, flowers and terrace. Move and slightly scale down the group into a COMPACT ensemble across the CENTER-RIGHT, with head centers around x=53%, x=65%, x=76% of total width, between y=34% and 44%. In particular move the blue-haired girl LEFT so her entire head and upper body lie inside the 80% width mark. Leave outer RIGHT 18% as decorative wall, flowers, shutters and breathing room, not a fourth person. The LEFT 42% should remain landscape for dark website text; no people there. Camera slightly farther away, all three with balanced importance, no single portrait. This change makes a wide 16:9 wallpaper survive a narrower browser crop. No text, logos, watermark or UI.
```

## seaside_friends_mobile.png

前版窄屏欢迎背景。内置 imagegen 根据横屏群像生成的竖屏构图，避免小屏只剩一个人；图片与文字分区，检查过 390px 视口。

提示词：
```text
Recompose this reference scene into a PORTRAIT mobile welcome wallpaper, approximately 1024x1536. Preserve the same cheerful hand-drawn 2D anime style, three distinct friends with silver-white, pastel-pink, sky-blue hair, modest pastel dresses, coastal village and garden terrace. All THREE friends must remain clearly visible together in the upper middle of a portrait composition; equal emphasis, natural tea-time interaction, smaller figures in environment, no single dominant portrait. Faces around 30%-43% from top, arranged across the middle 75% width with margins. Leave pale bright open sky / light wisteria in top 18% for tiny navigation overlays, and a very quiet pale mint / sunlit cream terrace foreground in the LOWER 40% for DARK mobile page copy. Maintain a bright sunny blue sea and pretty flowers. Flat expressive anime face drawing, not photoreal or 3D doll faces. No letters, text, branding, frames or UI.
```

## sidebar_garden.svg

手写矢量装饰：枝叶、星轨与星点，用于左右侧栏背景，不拦截点击，不增加右栏功能。

## favicon.png

沿用现有灵栖网页 logo，同时用于页签和聊天页左上品牌标识。

## 首页下方与左侧栏光效（2026-10-31）

上一版首页下方使用 `main_botton.png`，由 `home-motion.css` 将背景作为独立层轻微摆动，叠加光照；现已由下文的 `home_panel.png` 替换。`memory.png`、`like.png`、`world.png` 的错时闪光仍保留。上半区 `main.png` 未重绘，现作为独立全视口底图，升起的面板覆盖它的下部。聊天左栏在 `sidebar_garden.svg` 原有星星坐标叠加原生 HTML/CSS 微光；以上动态尊重减少动态效果设置。

## home_panel.png

使用内置 imagegen，参考并编辑 `main_botton.png`，生成浅紫白色的羽毛、花瓣、叶片背景。建筑、箭头、文档与行星装饰已移除，避免实体建筑随背景漂浮；左侧柔和植物影与中心留白保留。PNG 为 2172×724、不透明；生成结果已复制到本目录供项目实际引用，原图保留作旧素材。

在首页中，主图独立铺满视口，这张面板从屏幕底部上升到原有卡片区位置，再显示三张卡片；面板到位后，装饰背景继续轻微摆动。房子不再出现在动态背景中，卡片右下角的城市小图标仍只做扫光。

最终提示词（内置 imagegen 编辑模式，输入为 main_botton.png）：

```text
Use case: precise-object-edit. Asset type: very wide, subtle decorative website panel background. Edit this supplied pale lilac-white background for a gentle animated feature-card panel. Preserve its approximately 3:1 wide composition, very pale lavender/ivory/icy blue palette, abundant quiet empty center, low contrast, soft translucent botanical shadows along the lower left and lower right, delicate diffuse light and smooth finish. Remove ALL architecture, houses, buildings, towers, flags, city skylines and the rigid upward arrow. Replace the building on the far right with a small loose arrangement of translucent floating feather shapes, a few soft pink/lavender petals and pale sage leaf silhouettes, with plenty of space between them; these motifs should feel natural when the panel background drifts gently. Also remove the existing document/planet icon silhouettes, replacing with very sparse abstract floating petals so there are no rigid objects in this backdrop. This is a background behind three white cards, so decoration must remain faint and stay toward the outer edges and bottom. No people, no text, no lettering, no UI cards, no borders, no watermark. Do not change the calm airy overall style. Save as an opaque landscape PNG; the background must be completely painted, not transparent.
```


## voice_garden.png

心声页的月下庭园背景。使用内置 image_gen 生成，1672×940 PNG，约 3 MB。静态背景配合 CSS 背景位移、花瓣和光点动画使用。没有人物或文案；角色图片通过原有受保护图片接口独立加载。

完整生成提示词：
```text
Use case: stylized-concept. Asset type: background illustration for a romantic Chinese character inner-voice reading page. Wide landscape 3:2 or 16:9. Create a richly painted ethereal moonlit flower garden with climbing pale blush roses, trailing wisteria, translucent floating rose petals, scattered warm luminous fireflies, ivory gauze ribbons and delicate gold constellations. Palette: dusky lilac, dusty rose, warm ivory, muted sage, champagne gold. Soft elegant anime watercolor illustration, finely detailed flowers concentrated along the left and right edges and corners; center has softly luminous mist with subtle garden silhouettes for readable UI overlays. Full illustrated scene, not a blank gradient. Romantic intimate atmosphere, natural light bloom and depth, hand-painted texture. No people, no text, no typography, no UI, no borders, no watermark. This is a decorative background, existing character portraits will be separate HTML images.
```


## voice_lace.svg

心声正文的玫瑰藤蔓角花，手写 SVG 向量素材，含粉玫瑰、薄荷叶片、金色细线和紫色卷枝，旋转复用四角。通过 /static/pictures/voice_lace.svg 引用；动态光点由 CSS 绘制。

前端视频统一存放在 `web/videos/`，素材说明见该目录的 README.md；图片目录不保存视频。


## Feeling symbols（2026-11-02）

`feeling_symbols.svg` 为代码绘制的可复用 SVG 图案，包含好感度爱心、真实心情花朵，以及十二种固定次要感受的独立图案。由 feeling-cards.js 和 feeling-cards.css 按类别配色并添加柔和发光；没有外部图片和生成工具编号。心声和真实状态页面继续复用 voice_garden.png 庭园背景。

- `world_jianghu.png`：世界设定页面的水墨山河武侠背景插画。

- `world_ink.png`：古代武侠世界卡片及详情页的水墨背景。
- `world_reality.png`：现实世界卡片及详情页的城市背景。

- `world_vampire.png`：血族统治世界的卡片与详情背景。
- `world_space.png`：未来星际世界的卡片与详情背景。
