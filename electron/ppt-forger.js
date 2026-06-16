const fs = require("fs");
const PizZip = require("pizzip");

function escapeXml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function assertTemplateExists(templatePath) {
  if (!fs.existsSync(templatePath)) {
    throw new Error(`PPT 템플릿을 찾지 못했습니다: ${templatePath}`);
  }
}

function isEditablePresentationXml(key) {
  return (key.startsWith("ppt/slides/slide") || key.startsWith("ppt/notesSlides/notesSlide")) && key.endsWith(".xml");
}

function replaceScalarPlaceholders(xml, data) {
  let nextXml = xml;
  for (const [placeholderKey, value] of Object.entries(data)) {
    if (placeholderKey === "ownershipTableData") continue;
    if (placeholderKey === "call_percent") {
      nextXml = nextXml.replace(/X%/g, `${value}%`);
      continue;
    }
    if (placeholderKey === "refixing_percent") {
      nextXml = nextXml.replace(/Y%/g, `${value}%`);
      continue;
    }
    nextXml = nextXml.split(`{{${placeholderKey}}}`).join(String(value));
  }
  return nextXml;
}

function rightAlignCellXml(cellXml) {
  if (cellXml.includes("<a:pPr ")) {
    return cellXml.replace(/<a:pPr /g, '<a:pPr algn="r" marR="10800" ');
  }
  if (cellXml.includes("<a:pPr/>")) {
    return cellXml.replace(/<a:pPr\/>/g, '<a:pPr algn="r" marR="10800"/>');
  }
  return cellXml
    .replace(/<a:p>/g, '<a:p><a:pPr algn="r" marR="10800"/>')
    .replace(/<a:p [^>]*>/g, (match) => `${match}<a:pPr algn="r" marR="10800"/>`);
}

function removeExtraTextRuns(cellXml) {
  const extraAtRegex = new RegExp("</a:t>.*?<a:t>.*?</a:t>", "s");
  let nextCellXml = cellXml;
  while (extraAtRegex.test(nextCellXml)) {
    nextCellXml = nextCellXml.replace(extraAtRegex, "</a:t>");
  }
  return nextCellXml;
}

function fillOwnershipCell(cellXml, cellData, cellIndex) {
  if (!cellData) {
    return cellXml.replace(new RegExp("<a:t>.*?</a:t>", "gs"), "");
  }

  const text = escapeXml(cellData);
  if (cellXml.includes("<a:t>")) {
    const replacedXml = cellXml.replace(new RegExp("<a:t>.*?</a:t>"), `<a:t>${text}</a:t>`);
    return cellIndex > 0 ? rightAlignCellXml(removeExtraTextRuns(replacedXml)) : removeExtraTextRuns(replacedXml);
  }

  const pPrTag = cellIndex > 0 ? '<a:pPr algn="r" marR="10800"/>' : "";
  const textRun = `${pPrTag}<a:r><a:rPr sz="1000"><a:latin typeface="맑은 고딕"/><a:ea typeface="맑은 고딕"/></a:rPr><a:t>${text}</a:t></a:r>`;
  if (cellXml.includes("<a:p>")) {
    return cellXml.replace("<a:p>", `<a:p>${textRun}`);
  }
  if (cellXml.includes("<a:p ")) {
    return cellXml.replace(new RegExp("<a:p [^>]*>"), (match) => `${match}${textRun}`);
  }
  return cellXml;
}

function fillOwnershipRow(rowXml, rowIndex, ownershipTableData) {
  if (rowIndex < 2 || rowIndex >= 12) return rowXml;

  const dataRow = rowIndex - 2;
  let cellIndex = 0;
  const tcRegex = new RegExp("<a:tc[^>]*>.*?</a:tc>", "gs");
  return rowXml.replace(tcRegex, (cellXml) => {
    if (cellIndex >= 11) return cellXml;
    const cellData = ownershipTableData[dataRow]?.[cellIndex];
    const nextCellXml = fillOwnershipCell(cellXml, cellData, cellIndex);
    cellIndex += 1;
    return nextCellXml;
  });
}

function fillOwnershipTable(tblXml, ownershipTableData) {
  if (!tblXml.includes("특관자1") && !tblXml.includes("주주명")) return tblXml;

  let rowIndex = 0;
  const trRegex = new RegExp("<a:tr[^>]*>.*?</a:tr>", "gs");
  return tblXml.replace(trRegex, (rowXml) => {
    const nextRowXml = fillOwnershipRow(rowXml, rowIndex, ownershipTableData);
    rowIndex += 1;
    return nextRowXml;
  });
}

function replaceOwnershipTables(xml, ownershipTableData) {
  if (!ownershipTableData) return xml;

  let nextXml = xml;
  let currentPos = nextXml.indexOf("<a:tbl>");
  while (currentPos !== -1) {
    const tblEnd = nextXml.indexOf("</a:tbl>", currentPos);
    if (tblEnd === -1) break;

    const tblXml = nextXml.substring(currentPos, tblEnd + 8);
    const newTblXml = fillOwnershipTable(tblXml, ownershipTableData);
    nextXml = nextXml.substring(0, currentPos) + newTblXml + nextXml.substring(tblEnd + 8);
    currentPos = nextXml.indexOf("<a:tbl>", currentPos + newTblXml.length);
  }
  return nextXml;
}

function renderPresentationXml(xml, data) {
  return replaceOwnershipTables(replaceScalarPlaceholders(xml, data), data.ownershipTableData);
}

async function generatePpt(templatePath, outputPath, data) {
  assertTemplateExists(templatePath);
  const content = fs.readFileSync(templatePath, "binary");
  const zip = new PizZip(content);

  for (const key of Object.keys(zip.files)) {
    if (isEditablePresentationXml(key)) {
      zip.file(key, renderPresentationXml(zip.files[key].asText(), data));
    }
  }
  fs.writeFileSync(outputPath, zip.generate({ type: "nodebuffer", compression: "DEFLATE" }));
  return outputPath;
}

module.exports = {
  generatePpt,
  renderPresentationXml,
};
