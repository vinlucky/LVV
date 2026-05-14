const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat, TableOfContents,
} = require("docx");
const fs = require("fs");

const STYLES = {
  default: {
    primary: "2E75B6",
    accent: "D6E4F0",
    headerFont: "Arial",
    bodyFont: "Arial",
  },
  academic: {
    primary: "1E2761",
    accent: "CADCFC",
    headerFont: "Georgia",
    bodyFont: "Calibri",
  },
  business: {
    primary: "0D9488",
    accent: "CCFBF1",
    headerFont: "Arial Black",
    bodyFont: "Arial",
  },
};

const DXA_PER_INCH = 1440;
const PAGE_WIDTH = 12240;
const PAGE_HEIGHT = 15840;
const MARGIN = 1440;
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN;

function buildDocument(outline, style) {
  const s = STYLES[style] || STYLES.default;
  const sections = outline.sections || [];

  const children = [];

  if (outline.title) {
    children.push(
      new Paragraph({
        heading: HeadingLevel.TITLE,
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
        children: [new TextRun({ text: outline.title, bold: true, size: 56, font: s.headerFont, color: s.primary })],
      })
    );
  }

  if (outline.subtitle) {
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 400 },
        children: [new TextRun({ text: outline.subtitle, size: 28, font: s.bodyFont, color: "666666" })],
      })
    );
  }

  if (outline.author || outline.date) {
    const metaParts = [];
    if (outline.author) metaParts.push(outline.author);
    if (outline.date) metaParts.push(outline.date);
    children.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 600 },
        children: [new TextRun({ text: metaParts.join(" | "), size: 22, font: s.bodyFont, color: "999999" })],
      })
    );
  }

  children.push(new Paragraph({ children: [new PageBreak()] }));

  for (const section of sections) {
    if (section.heading) {
      const level = section.level || 1;
      const headingMap = {
        1: HeadingLevel.HEADING_1,
        2: HeadingLevel.HEADING_2,
        3: HeadingLevel.HEADING_3,
      };
      children.push(
        new Paragraph({
          heading: headingMap[level] || HeadingLevel.HEADING_1,
          spacing: { before: 360, after: 200 },
          children: [new TextRun({ text: section.heading, bold: true, font: s.headerFont, color: s.primary })],
        })
      );
    }

    if (section.paragraphs) {
      for (const para of section.paragraphs) {
        if (typeof para === "string") {
          children.push(
            new Paragraph({
              spacing: { after: 200 },
              children: [new TextRun({ text: para, size: 24, font: s.bodyFont })],
            })
          );
        } else if (para.bold && para.text) {
          children.push(
            new Paragraph({
              spacing: { after: 200 },
              children: [new TextRun({ text: para.text, bold: true, size: 24, font: s.bodyFont })],
            })
          );
        }
      }
    }

    if (section.bullets) {
      for (const bullet of section.bullets) {
        children.push(
          new Paragraph({
            numbering: { reference: "bullets", level: 0 },
            spacing: { after: 120 },
            children: [new TextRun({ text: bullet, size: 24, font: s.bodyFont })],
          })
        );
      }
    }

    if (section.table) {
      const table = section.table;
      const headers = table.headers || [];
      const rows = table.rows || [];
      const colCount = headers.length || (rows[0] && rows[0].length) || 1;
      const colWidth = Math.floor(CONTENT_WIDTH / colCount);
      const columnWidths = Array(colCount).fill(colWidth);

      const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
      const borders = { top: border, bottom: border, left: border, right: border };

      const tableRows = [];

      if (headers.length > 0) {
        tableRows.push(
          new TableRow({
            children: headers.map(
              (h) =>
                new TableCell({
                  borders,
                  width: { size: colWidth, type: WidthType.DXA },
                  shading: { fill: s.primary, type: ShadingType.CLEAR },
                  margins: { top: 80, bottom: 80, left: 120, right: 120 },
                  children: [
                    new Paragraph({
                      children: [new TextRun({ text: String(h), bold: true, size: 22, font: s.bodyFont, color: "FFFFFF" })],
                    }),
                  ],
                })
            ),
          })
        );
      }

      for (let rIdx = 0; rIdx < rows.length; rIdx++) {
        const row = rows[rIdx];
        const isEven = rIdx % 2 === 0;
        tableRows.push(
          new TableRow({
            children: row.map(
              (cell) =>
                new TableCell({
                  borders,
                  width: { size: colWidth, type: WidthType.DXA },
                  shading: isEven ? { fill: "F5F5F5", type: ShadingType.CLEAR } : undefined,
                  margins: { top: 60, bottom: 60, left: 120, right: 120 },
                  children: [
                    new Paragraph({
                      children: [new TextRun({ text: String(cell), size: 22, font: s.bodyFont })],
                    }),
                  ],
                })
            ),
          })
        );
      }

      children.push(
        new Table({
          width: { size: CONTENT_WIDTH, type: WidthType.DXA },
          columnWidths,
          rows: tableRows,
        })
      );

      children.push(new Paragraph({ spacing: { after: 200 }, children: [] }));
    }
  }

  const doc = new Document({
    styles: {
      default: { document: { run: { font: s.bodyFont, size: 24 } } },
      paragraphStyles: [
        {
          id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 36, bold: true, font: s.headerFont, color: s.primary },
          paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 },
        },
        {
          id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 30, bold: true, font: s.headerFont, color: s.primary },
          paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 },
        },
        {
          id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: 26, bold: true, font: s.headerFont, color: s.primary },
          paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 },
        },
      ],
    },
    numbering: {
      config: [
        {
          reference: "bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "\u2022",
              alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 720, hanging: 360 } } },
            },
          ],
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
            margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
          },
        },
        headers: {
          default: new Header({
            children: [
              new Paragraph({
                alignment: AlignmentType.RIGHT,
                children: [new TextRun({ text: outline.title || "", size: 18, font: s.bodyFont, color: "AAAAAA" })],
              }),
            ],
          }),
        },
        footers: {
          default: new Footer({
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [
                  new TextRun({ text: "Page ", size: 18, font: s.bodyFont, color: "AAAAAA" }),
                  new TextRun({ children: [PageNumber.CURRENT], size: 18, font: s.bodyFont, color: "AAAAAA" }),
                ],
              }),
            ],
          }),
        },
        children,
      },
    ],
  });

  return doc;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error("Usage: node render.js <outline.json> <output.docx> [style]");
    process.exit(1);
  }

  const outlinePath = args[0];
  const outputPath = args[1];
  const style = args[2] || "default";

  let outline;
  try {
    const raw = fs.readFileSync(outlinePath, "utf-8");
    outline = JSON.parse(raw);
  } catch (e) {
    console.error("Failed to read/parse outline JSON:", e.message);
    process.exit(1);
  }

  try {
    const doc = buildDocument(outline, style);
    const buffer = await Packer.toBuffer(doc);
    fs.writeFileSync(outputPath, buffer);
    console.log("OK:" + outputPath);
  } catch (e) {
    console.error("Failed to generate DOCX:", e.message);
    process.exit(1);
  }
}

main();
