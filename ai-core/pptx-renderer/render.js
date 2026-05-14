const pptxgen = require("pptxgenjs");
const fs = require("fs");

const STYLES = {
  academic: {
    primary: "1E2761",
    secondary: "CADCFC",
    bgTitle: "1E2761",
    bgContent: "FFFFFF",
    titleColor: "FFFFFF",
    subtitleColor: "CADCFC",
    bulletColor: "333333",
    headerFont: "Georgia",
    bodyFont: "Calibri",
  },
  business: {
    primary: "0D9488",
    secondary: "14B8A6",
    bgTitle: "0F766E",
    bgContent: "FFFFFF",
    titleColor: "FFFFFF",
    subtitleColor: "99F6E4",
    bulletColor: "334155",
    headerFont: "Arial Black",
    bodyFont: "Arial",
  },
  creative: {
    primary: "F96167",
    secondary: "F9E795",
    bgTitle: "2F3C7E",
    bgContent: "FFF8F0",
    titleColor: "FFFFFF",
    subtitleColor: "F9E795",
    bulletColor: "333333",
    headerFont: "Trebuchet MS",
    bodyFont: "Calibri",
  },
};

const makeShadow = () => ({
  type: "outer",
  blur: 6,
  offset: 2,
  angle: 135,
  color: "000000",
  opacity: 0.1,
});

function buildPresentation(outline, style) {
  const s = STYLES[style] || STYLES.academic;
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.author = outline.author || "AI Assistant";
  pres.title = outline.title || "Presentation";

  const slides = outline.slides || [];

  addTitleSlide(pres, outline, s);
  addAgendaSlide(pres, outline, s);

  for (let i = 0; i < slides.length; i++) {
    const slideData = slides[i];
    const bullets = slideData.bullets || [];
    if (bullets.length <= 3) {
      addCardSlide(pres, slideData, s);
    } else {
      addTwoColumnSlide(pres, slideData, s);
    }
  }

  addEndSlide(pres, outline, s);
  return pres;
}

function addTitleSlide(pres, outline, s) {
  const slide = pres.addSlide();
  slide.background = { color: s.bgTitle };

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.3, h: 7.5,
    fill: { color: s.bgTitle },
  });

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.8, y: 2.8, w: 0.08, h: 1.6,
    fill: { color: s.secondary },
  });

  slide.addText(outline.title || "未命名", {
    x: 1.2, y: 2.5, w: 10, h: 1.2,
    fontSize: 40, fontFace: s.headerFont,
    color: s.titleColor, bold: true, margin: 0,
  });

  slide.addText(outline.subtitle || "", {
    x: 1.2, y: 3.8, w: 10, h: 0.6,
    fontSize: 20, fontFace: s.bodyFont,
    color: s.subtitleColor, margin: 0,
  });

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 1.2, y: 5.0, w: 3, h: 0.02,
    fill: { color: s.secondary },
  });

  if (outline.author) {
    slide.addText(outline.author, {
      x: 1.2, y: 5.3, w: 5, h: 0.4,
      fontSize: 14, fontFace: s.bodyFont,
      color: s.subtitleColor, margin: 0,
    });
  }
}

function addAgendaSlide(pres, outline, s) {
  const slides = outline.slides || [];
  if (slides.length === 0) return;

  const slide = pres.addSlide();
  slide.background = { color: s.bgContent };

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.3, h: 1.2,
    fill: { color: s.primary },
  });

  slide.addText("目录", {
    x: 0.8, y: 0.2, w: 10, h: 0.8,
    fontSize: 28, fontFace: s.headerFont,
    color: s.titleColor, bold: true, margin: 0,
  });

  const itemsPerCol = Math.ceil(slides.length / 2);
  const col1Items = slides.slice(0, itemsPerCol);
  const col2Items = slides.slice(itemsPerCol);

  const renderAgendaItems = (items, startX, offset) => {
    items.forEach((item, idx) => {
      const yPos = 1.6 + idx * 0.7;

      slide.addShape(pres.shapes.OVAL, {
        x: startX, y: yPos + 0.08, w: 0.35, h: 0.35,
        fill: { color: s.primary },
      });

      slide.addText(String(offset + idx + 1), {
        x: startX, y: yPos + 0.08, w: 0.35, h: 0.35,
        fontSize: 11, fontFace: s.bodyFont,
        color: s.titleColor, align: "center", valign: "middle", margin: 0,
      });

      slide.addText(item.title || "", {
        x: startX + 0.55, y: yPos, w: 5, h: 0.5,
        fontSize: 16, fontFace: s.bodyFont,
        color: s.bulletColor, valign: "middle", margin: 0,
      });
    });
  };

  renderAgendaItems(col1Items, 1.0, 0);
  renderAgendaItems(col2Items, 7.0, itemsPerCol);

  addFooter(pres, slide);
}

function addCardSlide(pres, slideData, s) {
  const slide = pres.addSlide();
  slide.background = { color: s.bgContent };

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.3, h: 1.2,
    fill: { color: s.primary },
  });

  slide.addText(slideData.title || "", {
    x: 0.8, y: 0.2, w: 11, h: 0.8,
    fontSize: 26, fontFace: s.headerFont,
    color: s.titleColor, bold: true, margin: 0,
  });

  const bullets = slideData.bullets || [];
  const cardStartY = 1.6;
  const cardHeight = Math.min(1.2, (5.5 - 0.3 * (bullets.length - 1)) / bullets.length);
  const cardGap = 0.3;

  bullets.forEach((bullet, bIdx) => {
    const yPos = cardStartY + bIdx * (cardHeight + cardGap);

    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0.8, y: yPos, w: 11.5, h: cardHeight,
      fill: { color: "FFFFFF" }, shadow: makeShadow(),
    });

    slide.addShape(pres.shapes.RECTANGLE, {
      x: 0.8, y: yPos, w: 0.06, h: cardHeight,
      fill: { color: s.primary },
    });

    slide.addText(bullet, {
      x: 1.2, y: yPos, w: 10.8, h: cardHeight,
      fontSize: 16, fontFace: s.bodyFont,
      color: s.bulletColor, valign: "middle", margin: 0,
    });
  });

  if (slideData.notes) {
    slide.addNotes(slideData.notes);
  }

  addFooter(pres, slide);
}

function addTwoColumnSlide(pres, slideData, s) {
  const slide = pres.addSlide();
  slide.background = { color: s.bgContent };

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.3, h: 1.2,
    fill: { color: s.primary },
  });

  slide.addText(slideData.title || "", {
    x: 0.8, y: 0.2, w: 11, h: 0.8,
    fontSize: 26, fontFace: s.headerFont,
    color: s.titleColor, bold: true, margin: 0,
  });

  const bullets = slideData.bullets || [];
  const half = Math.ceil(bullets.length / 2);
  const leftBullets = bullets.slice(0, half);
  const rightBullets = bullets.slice(half);

  const renderBullets = (items, startX) => {
    const bulletTexts = items.map((text, bIdx) => ({
      text: text,
      options: {
        bullet: true,
        breakLine: bIdx < items.length - 1,
        indentLevel: 0,
        fontSize: 15,
        fontFace: s.bodyFont,
        color: s.bulletColor,
        paraSpaceAfter: 8,
      },
    }));

    slide.addText(bulletTexts, {
      x: startX, y: 1.6, w: 5.5, h: 5.2,
      valign: "top", margin: [0, 0, 0, 0],
    });
  };

  renderBullets(leftBullets, 0.8);
  renderBullets(rightBullets, 6.8);

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 6.5, y: 1.8, w: 0.02, h: 4.5,
    fill: { color: "E2E8F0" },
  });

  if (slideData.notes) {
    slide.addNotes(slideData.notes);
  }

  addFooter(pres, slide);
}

function addEndSlide(pres, outline, s) {
  const slide = pres.addSlide();
  slide.background = { color: s.bgTitle };

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 13.3, h: 7.5,
    fill: { color: s.bgTitle },
  });

  slide.addText("谢谢", {
    x: 1, y: 2.5, w: 11, h: 1.5,
    fontSize: 48, fontFace: s.headerFont,
    color: s.titleColor, bold: true,
    align: "center", valign: "middle", margin: 0,
  });

  slide.addText(outline.title || "", {
    x: 1, y: 4.2, w: 11, h: 0.6,
    fontSize: 18, fontFace: s.bodyFont,
    color: s.subtitleColor,
    align: "center", valign: "middle", margin: 0,
  });

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 5.5, y: 5.1, w: 2.3, h: 0.02,
    fill: { color: s.secondary },
  });
}

function addFooter(pres, slide) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 7.1, w: 13.3, h: 0.4,
    fill: { color: "F8FAFC" },
  });

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 7.08, w: 13.3, h: 0.02,
    fill: { color: "E2E8F0" },
  });
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error("Usage: node render.js <outline.json> <output.pptx> [style]");
    process.exit(1);
  }

  const outlinePath = args[0];
  const outputPath = args[1];
  const style = args[2] || "academic";

  let outline;
  try {
    const raw = fs.readFileSync(outlinePath, "utf-8");
    outline = JSON.parse(raw);
  } catch (e) {
    console.error("Failed to read/parse outline JSON:", e.message);
    process.exit(1);
  }

  try {
    const pres = buildPresentation(outline, style);
    await pres.writeFile({ fileName: outputPath });
    console.log("OK:" + outputPath);
  } catch (e) {
    console.error("Failed to generate PPTX:", e.message);
    process.exit(1);
  }
}

main();
