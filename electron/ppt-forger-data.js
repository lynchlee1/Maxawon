const ExcelJS = require("exceljs");
const fs = require("fs");

function getCellValue(cell) {
  if (!cell || cell.value === undefined || cell.value === null) return null;
  if (typeof cell.value === "object" && cell.value.result !== undefined) return cell.value.result;
  return cell.value;
}

function parseNumber(value) {
  if (typeof value === "number") return value;
  if (!value) return 0;
  return parseFloat(String(value).replace(/,/g, "").replace(/[^0-9.-]/g, "")) || 0;
}

function parseInteger(value) {
  return Math.floor(parseNumber(value));
}

function parseKrwAmount(value) {
  const numeric = parseNumber(value);
  if (!numeric) return 0;
  if (String(value).includes("조")) return numeric * 1_000_000_000_000;
  if (String(value).includes("억")) return numeric * 100_000_000;
  return numeric * 100_000_000;
}

function formatPercentLabel(value) {
  const parsed = parseNumber(value);
  return Number.isInteger(parsed) ? String(parsed) : String(parsed);
}

function hasBatchim(word) {
  if (!word) return false;
  const lastChar = word.charCodeAt(word.length - 1);
  if (lastChar < 0xac00 || lastChar > 0xd7a3) return false;
  return (lastChar - 0xac00) % 28 !== 0;
}

function getMezzType(mezzTypeFull) {
  const full = mezzTypeFull || "";
  if (full.includes("신주인수권부사채") || full.toUpperCase().includes("BW")) {
    return { kor: "신주인수권부사채", eng: "BW" };
  }
  if (full.includes("전환사채") || full.toUpperCase().includes("CB")) {
    return { kor: "전환사채", eng: "CB" };
  }
  if (full.includes("교환사채") || full.toUpperCase().includes("EB")) {
    return { kor: "교환사채", eng: "EB" };
  }
  return { kor: "", eng: "" };
}

async function extractPriceTrendData(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`엑셀 파일을 찾지 못했습니다: ${filePath}`);
  }

  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(filePath);
  const worksheet = workbook.getWorksheet("#주가");
  if (!worksheet) {
    throw new Error("엑셀 파일에서 #주가 시트를 찾지 못했습니다.");
  }

  const exercisePrice = getCellValue(worksheet.getCell("H6"));
  const premiumRate = getCellValue(worksheet.getCell("H3"));
  const baseDateExcel = getCellValue(worksheet.getCell("H2"));

  const data = [];
  let latestMarketCap = null;

  for (let rowIndex = 14; rowIndex <= worksheet.rowCount; rowIndex += 1) {
    const row = worksheet.getRow(rowIndex);
    const rowList = [];
    let isRowEmpty = true;
    for (let colIndex = 1; colIndex <= 5; colIndex += 1) {
      const value = getCellValue(row.getCell(colIndex));
      rowList.push(value);
      if (value !== null) isRowEmpty = false;
    }
    if (isRowEmpty) continue;

    data.push(rowList);
    const dateValue = rowList[0];
    const marketCapValue = rowList[4];
    if (marketCapValue !== null && dateValue !== "D A T E") {
      latestMarketCap = marketCapValue;
    }
  }

  return {
    data,
    latest_market_cap: latestMarketCap,
    exercise_price: exercisePrice,
    premium_rate: premiumRate,
    base_date: baseDateExcel instanceof Date ? baseDateExcel.toISOString() : baseDateExcel,
  };
}

async function extractFinancialData(filePath) {
  if (!fs.existsSync(filePath)) return { data: {}, missing: [] };

  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.readFile(filePath);
  const worksheet = workbook.getWorksheet("#보고서");
  if (!worksheet) return { data: {}, missing: [] };

  const headerRow = worksheet.getRow(6);
  let sepCol23 = -1;
  let sepCol24 = -1;
  let sepCol25 = -1;
  let conCol23 = -1;
  let conCol24 = -1;
  let conCol25 = -1;

  for (let colIndex = 1; colIndex <= headerRow.cellCount; colIndex += 1) {
    const value = String(getCellValue(headerRow.getCell(colIndex))).trim();
    if (colIndex <= 14) {
      if (value === "2023") sepCol23 = colIndex;
      if (value === "2024") sepCol24 = colIndex;
      if (value === "2025E" || value === "2025") sepCol25 = colIndex;
    } else {
      if (value === "2023") conCol23 = colIndex;
      if (value === "2024") conCol24 = colIndex;
      if (value === "2025E" || value === "2025") conCol25 = colIndex;
    }
  }

  const targets = ["자산총계", "순차입금", "부채비율", "차입금의존도", "매출액", "영업이익", "영업이익률", "당기순이익", "당기순이익률"];
  const parsedData = {};
  const missing = [];

  const matchLabel = (label, target) => {
    const cleanLabel = label.replace(/\s/g, "");
    if (target === "당기순이익") return cleanLabel.startsWith("당기순이익") && !cleanLabel.includes("률");
    if (target === "영업이익") return cleanLabel.startsWith("영업이익") && !cleanLabel.includes("률");
    return cleanLabel.includes(target);
  };

  const extractRowData = (rowNumber, isCon) => {
    const row = worksheet.getRow(rowNumber);
    const col23 = isCon ? conCol23 : sepCol23;
    const col24 = isCon ? conCol24 : sepCol24;
    const col25 = isCon ? conCol25 : sepCol25;
    return {
      2023: col23 !== -1 ? getCellValue(row.getCell(col23)) : null,
      2024: col24 !== -1 ? getCellValue(row.getCell(col24)) : null,
      2025: col25 !== -1 ? getCellValue(row.getCell(col25)) : null,
    };
  };

  for (const target of targets) {
    let foundConRow = -1;
    let foundSepRow = -1;

    for (let rowIndex = 1; rowIndex <= worksheet.rowCount; rowIndex += 1) {
      const row = worksheet.getRow(rowIndex);
      const sepLabel = String(getCellValue(row.getCell(2)) || "").trim();
      const conLabel = String(getCellValue(row.getCell(16)) || "").trim();
      if (matchLabel(conLabel, target)) foundConRow = rowIndex;
      if (matchLabel(sepLabel, target)) foundSepRow = rowIndex;
    }

    if (foundConRow !== -1) parsedData[target] = extractRowData(foundConRow, true);
    else if (foundSepRow !== -1) parsedData[target] = extractRowData(foundSepRow, false);
    else missing.push(target);
  }

  return { data: parsedData, missing };
}

async function readExcelData(filePath) {
  const priceData = await extractPriceTrendData(filePath);
  const financialData = await extractFinancialData(filePath);
  return {
    ...priceData,
    financialData: financialData.data,
    missingFinancials: financialData.missing,
  };
}

function cleanStockCode(stockCode) {
  const cleanCode = String(stockCode || "").trim();
  if (!/^\d{6}$/.test(cleanCode)) {
    throw new Error("종목코드는 6자리 숫자로 입력하세요.");
  }
  return cleanCode;
}

function normalizeMarket(value) {
  const text = String(value || "").trim();
  if (text === "KSE" || text.includes("유가증권") || text.includes("코스피")) return "KOSPI";
  if (text.includes("코스닥")) return "KOSDAQ";
  if (text.includes("코넥스")) return "KONEX";
  return text;
}

async function fetchFnGuideHtml(cleanCode) {
  const fnguideUrl = `https://comp.fnguide.com/SVO2/ASP/SVD_main.asp?pGB=1&gicode=A${cleanCode}&cID=&MenuYn=Y&ReportGB=&NewMenuID=11&stkGb=&strResearchYN=`;
  const fnResponse = await fetch(fnguideUrl);
  return fnResponse.text();
}

function parseFnGuideProfile(fnHtml) {
  const nameMatch = fnHtml.match(/<h1[^>]*id="giName"[^>]*>([^<]+)<\/h1>/i) || fnHtml.match(/<title>([^|]+)\|/i);
  const marketMatch = fnHtml.match(/<input[^>]*id="strMarket"[^>]*value="([^"]+)"/i);
  const marketTxtMatch = fnHtml.match(/<span[^>]*id="strMarketTxt"[^>]*>([^<]+)<\/span>/i);

  return {
    companyName: nameMatch ? nameMatch[1].trim() : "",
    stockMarket: normalizeMarket(marketTxtMatch ? marketTxtMatch[1].trim() : marketMatch?.[1]?.trim()),
  };
}

function buildKindSearchBody(cleanCode) {
  const searchBody = new URLSearchParams();
  searchBody.append("method", "searchCorpNameJson");
  searchBody.append("isurCd", "");
  searchBody.append("kisComCd", "");
  searchBody.append("repIsuCd", "");
  searchBody.append("mode", "");
  searchBody.append("tabMenu", "0");
  searchBody.append("companyNM", "");
  searchBody.append("searchCodeType", "");
  searchBody.append("searchCorpName", cleanCode);
  searchBody.append("spotIsuTrdMktTpCd", "");
  searchBody.append("comAttrTpCd", "");
  searchBody.append("comAbbrv", "");
  return searchBody;
}

async function fetchKindCorpInfo(cleanCode) {
  const kindSearchResponse = await fetch("https://kind.krx.co.kr/common/searchcorpname.do", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: buildKindSearchBody(cleanCode).toString(),
  });
  const kindSearchResults = await kindSearchResponse.json();
  if (!kindSearchResults || kindSearchResults.length === 0) {
    throw new Error(`KIND에서 종목코드 ${cleanCode} 회사를 찾지 못했습니다.`);
  }
  return kindSearchResults[0];
}

function buildKindInfoBody(corpInfo, companyName) {
  const infoBody = new URLSearchParams();
  infoBody.append("method", "searchTotalInfo");
  infoBody.append("isurCd", corpInfo.isurcd);
  infoBody.append("kisComCd", corpInfo.kiscomcd);
  infoBody.append("repIsuCd", corpInfo.repisucd);
  infoBody.append("mode", "");
  infoBody.append("tabMenu", "0");
  infoBody.append("companyNM", encodeURIComponent(companyName));
  infoBody.append("searchCodeType", "");
  infoBody.append("searchCorpName", companyName);
  infoBody.append("spotIsuTrdMktTpCd", corpInfo.spotisutrdmkttpcd || "1");
  infoBody.append("comAttrTpCd", corpInfo.comAttrTpCd || "1");
  infoBody.append("comAbbrv", companyName);
  return infoBody;
}

async function fetchKindInfoHtml(corpInfo, companyName) {
  const kindInfoResponse = await fetch("https://kind.krx.co.kr/corpdetail/totalinfo.do", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: buildKindInfoBody(corpInfo, companyName).toString(),
  });
  return kindInfoResponse.text();
}

function parseKindCompanyData(kindInfoHtml) {
  const extractField = (label) => {
    const regex = new RegExp(`<th[^>]*>[^<]*${label}[^<]*<\\/th>\\s*<td[^>]*>([^<]*)<\\/td>`, "i");
    const match = kindInfoHtml.match(regex);
    return match ? match[1].trim().replace(/&nbsp;/g, " ") : "";
  };

  const companyData = {
    corp_name_en: extractField("영문명"),
    establishment_date: extractField("설립일"),
    representative: extractField("대표이사"),
    listing_date: extractField("상장일"),
    capital: extractField("자본금"),
    employees: extractField("종업원수"),
    fiscal_month: extractField("결산월"),
    phone: extractField("전화번호"),
    industry: extractField("업종"),
    main_products: extractField("주요제품"),
    address: extractField("주소"),
    homepage: extractField("홈페이지"),
  };
}

function buildKindSummaryBody(corpInfo) {
  const summaryBody = new URLSearchParams();
  summaryBody.append("method", "searchCompanySummaryOvrvwDetail");
  summaryBody.append("strIsurCd", corpInfo.isurcd.substring(0, 5));
  summaryBody.append("lstCd", "undefined");
  return summaryBody;
}

async function fetchKindSummaryHtml(corpInfo) {
  const kindSummaryResponse = await fetch("https://kind.krx.co.kr/common/companysummary.do", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: buildKindSummaryBody(corpInfo).toString(),
  });
  return kindSummaryResponse.text();
}

function parseKindSummary(kindSummaryHtml, fallbackCompanyName, fallbackMarket) {
  const corpNameMatch = kindSummaryHtml.match(/<th scope="row">한글명<\/th>\s*<td>\s*(?:<img[^>]*>\s*&nbsp;)?\s*([^<\s\n\r\t]+)\s*<\/td>/i);
  const corpName = corpNameMatch ? corpNameMatch[1].trim() : fallbackCompanyName;

  const marketTypeMatch = kindSummaryHtml.match(/<th scope="row">시장구분<\/th>\s*<td>\s*<strong[^>]*>([^<]+)<\/strong>/i);
  const corpNameFullMatch = kindSummaryHtml.match(/<h2[^>]*>상호변경내역<\/h2>.*?<tbody>\s*<tr>\s*<td[^>]*>.*?<\/td>\s*<td[^>]*>.*?<\/td>\s*<td[^>]*>(.*?)<\/td>/is);

  return {
    corpName,
    corpNameFull: corpNameFullMatch ? corpNameFullMatch[1].trim() : `${corpName}(주)`,
    stockMarket: normalizeMarket(marketTypeMatch ? marketTypeMatch[1].trim() : fallbackMarket),
  };
}

function parseTotalIssuedShares(fnHtml) {
  const sharesMatch = fnHtml.match(/발행주식수(?:<span[^>]*>[^<]*<\/span>)?<\/div>\s*<\/th>\s*<td[^>]*>([^<]+)<\/td>/i);
  return sharesMatch ? parseInt(sharesMatch[1].split("/")[0].replace(/,/g, "").trim(), 10) || 0 : 0;
}

function parseFnGuideShareClassification(fnHtml) {
  const shareholderClassification = [];
  const classificationTableMatch = fnHtml.match(/<div[^>]*id="svdMainGrid5".*?<tbody>(.*?)<\/tbody>/is);
  if (!classificationTableMatch) return shareholderClassification;

  const rowRegex = /<tr><th[^>]*><div>(.*?)<\/div><\/th><td[^>]*>(.*?)<\/td><td[^>]*>(.*?)<\/td><td[^>]*>(.*?)<\/td><td[^>]*>(.*?)<\/td><\/tr>/gis;
  const targetCategories = ["최대주주등", "자기주식", "우리사주조합"];
  let match;
  while ((match = rowRegex.exec(classificationTableMatch[1])) !== null) {
    const category = match[1].replace(/&nbsp;/g, " ").trim();
    const foundTarget = targetCategories.find((target) => category.startsWith(target));
    if (foundTarget) {
      shareholderClassification.push({
        category: foundTarget,
        shares: match[3].replace(/&nbsp;/g, "").trim() || "0",
      });
    }
  }
  return shareholderClassification;
}

async function fetchFnGuideShareholders(cleanCode) {
  const shareholdersResponse = await fetch(`https://comp.fnguide.com/SVO2/json/data/01_09_01/A${cleanCode}.json`);
  const shareholdersData = await shareholdersResponse.json();
  if (!shareholdersData || !shareholdersData.comp) return [];

  return shareholdersData.comp
    .filter((shareholder) => shareholder.SHER_GB_1 === "10")
    .map((shareholder) => ({
      name: shareholder.SHER_NM,
      relation: shareholder.MAJ_REL_NM,
      shares: shareholder.COMM_STK_QTY,
      ratio: shareholder.SHER_RT,
      callEnabled: true,
    }));
}

async function fetchFnGuideShareData(cleanCode, fnHtml) {
  let totalIssuedShares = 0;
  let shareholders = [];
  const shareholderClassification = [];

  try {
    totalIssuedShares = parseTotalIssuedShares(fnHtml);
    shareholderClassification.push(...parseFnGuideShareClassification(fnHtml));
    shareholders = await fetchFnGuideShareholders(cleanCode);
  } catch (_error) {
    // FnGuide supplementary tables may be absent for some companies.
  }
  return { totalIssuedShares, shareholders, shareholderClassification };
}

async function fetchCompanyInfo(stockCode) {
  const cleanCode = cleanStockCode(stockCode);
  const fnHtml = await fetchFnGuideHtml(cleanCode);
  const fnGuideProfile = parseFnGuideProfile(fnHtml);
  const corpInfo = await fetchKindCorpInfo(cleanCode);
  const companyName = corpInfo.repisusrtkornm || fnGuideProfile.companyName;
  const [kindInfoHtml, kindSummaryHtml, shareData] = await Promise.all([
    fetchKindInfoHtml(corpInfo, companyName),
    fetchKindSummaryHtml(corpInfo),
    fetchFnGuideShareData(cleanCode, fnHtml),
  ]);
  const summary = parseKindSummary(kindSummaryHtml, companyName, fnGuideProfile.stockMarket);

  return {
    corp_name: summary.corpName,
    corp_name_full: summary.corpNameFull,
    stock_market: summary.stockMarket,
    companyData: parseKindCompanyData(kindInfoHtml),
    ...shareData,
  };
}

function makeDerivedCompanyFields(companyInfo, excelData, inputs) {
  const today = new Date();
  const nextMonday = new Date(today);
  const daysUntilMonday = (1 + 7 - today.getDay()) % 7;
  nextMonday.setDate(today.getDate() + (daysUntilMonday === 0 ? 7 : daysUntilMonday));
  const reportDate = `${nextMonday.getFullYear()}. ${String(nextMonday.getMonth() + 1).padStart(2, "0")}. ${String(nextMonday.getDate()).padStart(2, "0")}`;

  let baseDate = "";
  if (excelData.base_date) {
    const parsedDate = new Date(excelData.base_date);
    baseDate = Number.isNaN(parsedDate.getTime())
      ? String(excelData.base_date)
      : `${String(parsedDate.getMonth() + 1).padStart(2, "0")}/${String(parsedDate.getDate()).padStart(2, "0")}`;
  } else {
    baseDate = `${String(today.getMonth() + 1).padStart(2, "0")}/${String(today.getDate()).padStart(2, "0")}`;
  }

  let premiumRate = 0;
  if (typeof excelData.premium_rate === "number") premiumRate = excelData.premium_rate;
  else if (typeof excelData.premium_rate === "string") premiumRate = parseFloat(excelData.premium_rate.replace(/[^0-9.]/g, "")) || 0;
  if (premiumRate > 0 && premiumRate < 1) premiumRate *= 100;

  const exercisePrice = typeof excelData.exercise_price === "number" ? Math.floor(excelData.exercise_price) : parseNumber(excelData.exercise_price);
  const investmentAmount = parseFloat(String(inputs.investment_amt || "").replace(/[^0-9.]/g, ""));
  const newIssuedShares = !Number.isNaN(investmentAmount) && exercisePrice > 0 ? Math.floor((investmentAmount * 100_000_000) / exercisePrice) : null;

  return {
    nameEnd: hasBatchim(companyInfo.corp_name) ? "이" : "가",
    reportDate,
    baseDate,
    premiumText: premiumRate > 0 ? `${premiumRate}% 할증` : "기준가 par 발행",
    exercisePrice,
    newIssuedShares,
  };
}

function buildDisplayedShareholders(shareholders, maxShareholders) {
  if (shareholders.length <= maxShareholders) return shareholders;
  const top = shareholders.slice(0, maxShareholders);
  const rest = shareholders.slice(maxShareholders);
  const otherShares = rest.reduce((sum, shareholder) => sum + parseInteger(shareholder.shares), 0);
  const otherRatio = rest.reduce((sum, shareholder) => sum + parseNumber(shareholder.ratio), 0);
  return [
    ...top,
    {
      name: "기타특관자",
      relation: "특수관계인",
      shares: otherShares.toLocaleString(),
      ratio: otherRatio.toFixed(2),
      callEnabled: rest.some((shareholder) => shareholder.callEnabled !== false),
    },
  ];
}

function buildOwnershipCases(options) {
  const baseTotal = options.totalIssuedShares || 0;
  const basePrice = options.exercisePrice || 0;
  const issueAmount = parseKrwAmount(options.issueAmt);
  const investmentAmount = parseKrwAmount(options.investmentAmt);
  const coInvestmentAmount = Math.max(issueAmount - investmentAmount, 0);
  const priorShares = parseInteger(options.priorMezzanineShares);
  const callRate = Math.min(Math.max(parseNumber(options.callPercent) / 100, 0), 1);
  const refixingRate = Math.min(Math.max(parseNumber(options.refixingPercent) / 100, 0), 1);
  const hasCall = callRate > 0;
  const hasRefixing = refixingRate > 0;

  const majorRows = options.displayedShareholdersWithRatio.map((shareholder) => ({
    name: shareholder.name,
    shares: parseInteger(shareholder.shares),
    isMajor: true,
    callEnabled: shareholder.callEnabled !== false,
    ratio: parseNumber(shareholder.ratio) / 100,
  }));
  const majorShares = majorRows.reduce((sum, row) => sum + row.shares, 0);
  const treasuryFromClassification = options.shareholderClassification
    .filter((item) => /자기주식|자사주/.test(item.category))
    .reduce((sum, item) => sum + parseInteger(item.shares), 0);
  const treasuryAlreadyInMajor = majorRows.some((row) => /자기주식|자사주/.test(row.name));
  const treasuryShares = treasuryAlreadyInMajor ? 0 : treasuryFromClassification;

  const employeeShares = options.shareholderClassification
    .filter((item) => /우리사주/.test(item.category))
    .reduce((sum, item) => sum + parseInteger(item.shares), 0);
  const employeeAlreadyInMajor = majorRows.some((row) => /우리사주/.test(row.name));
  const separateEmployeeShares = employeeAlreadyInMajor ? 0 : employeeShares;
  const otherShares = Math.max(baseTotal - majorShares - treasuryShares - separateEmployeeShares, 0);

  const baseRows = [
    ...majorRows,
    ...(treasuryShares > 0 ? [{ name: "자사주", shares: treasuryShares, isTreasury: true }] : []),
    ...(separateEmployeeShares > 0 ? [{ name: "우리사주", shares: separateEmployeeShares }] : []),
    { name: "기타주주", shares: otherShares },
  ];

  const convertFaceValue = (amount, price) => {
    if (!amount || !price) return 0;
    return Math.floor(amount / price);
  };

  const convertWithFallback = (amount, price, activeRefixingRate) => {
    const converted = convertFaceValue(amount, price);
    if (converted > 0 || !investmentAmount || !options.newIssuedShares) return converted;
    const refixingMultiplier = activeRefixingRate > 0 ? 1 / activeRefixingRate : 1;
    return Math.floor(((options.newIssuedShares * amount) / investmentAmount) * refixingMultiplier);
  };

  const buildCase = (label, caseOptions) => {
    const price = caseOptions.refixingRate && caseOptions.refixingRate > 0 ? Math.floor(basePrice * caseOptions.refixingRate) : basePrice;
    const activeCallRate = caseOptions.callRate || 0;
    const activeRefixingRate = caseOptions.refixingRate || 0;
    const ownAmount = investmentAmount * (1 - activeCallRate);
    const coAmount = coInvestmentAmount * (1 - activeCallRate);
    const ownConverted = convertWithFallback(ownAmount, price, activeRefixingRate);
    const coConverted = convertWithFallback(coAmount, price, activeRefixingRate);
    const callPool = convertWithFallback(issueAmount * activeCallRate, price, activeRefixingRate);
    const totalConverted = ownConverted + coConverted + callPool;
    const rows = baseRows.map((row) => ({ ...row }));
    const treasuryRow = rows.find((row) => row.isTreasury);
    let remainingCallPool = callPool;

    if (activeCallRate > 0 && baseTotal > 0) {
      for (const row of rows) {
        if (!row.isMajor || row.callEnabled === false) continue;
        const beforeRatio = row.ratio !== undefined ? row.ratio : row.shares / baseTotal;
        const exercisableShares = Math.floor(beforeRatio * totalConverted);
        const calledShares = Math.min(exercisableShares, remainingCallPool);
        row.shares += calledShares;
        remainingCallPool -= calledShares;
        if (remainingCallPool <= 0) break;
      }

      if (remainingCallPool > 0) {
        if (treasuryRow) treasuryRow.shares += remainingCallPool;
        else rows.push({ name: "자사주", shares: remainingCallPool, isTreasury: true });
      }
    }

    if (options.isTreasuryEb && treasuryRow) {
      treasuryRow.shares = Math.max(treasuryRow.shares - totalConverted, 0);
    }

    rows.push({ name: `${options.mezzTypeEng || "CB"}(당사)`, shares: ownConverted });
    rows.push({ name: `${options.mezzTypeEng || "CB"}(공동투자자)`, shares: coConverted });
    rows.push({ name: "기발행 메자닌", shares: priorShares });

    const actualTotalShares = rows.reduce((sum, row) => sum + row.shares, 0);
    return { label, rows, totalShares: actualTotalShares, denominatorShares: actualTotalShares };
  };

  const baseTotalShares = baseRows.reduce((sum, row) => sum + row.shares, 0);
  const cases = [
    { label: "메자닌 발행 전", rows: baseRows, totalShares: baseTotalShares, denominatorShares: baseTotalShares },
    buildCase("금차 메자닌 전환 후", {}),
  ];
  if (hasCall) cases.push(buildCase(`Call ${formatPercentLabel(options.callPercent)}%`, { callRate }));
  if (hasRefixing) cases.push(buildCase(`리픽싱 ${formatPercentLabel(options.refixingPercent)}%`, { refixingRate }));
  if (hasCall && hasRefixing) cases.push(buildCase(`Call ${formatPercentLabel(options.callPercent)}%, 리픽싱 ${formatPercentLabel(options.refixingPercent)}%`, { callRate, refixingRate }));
  return cases;
}

function buildOwnershipTableData({ displayedShareholdersWithRatio, ownershipCases, mezzTypeEng }) {
  const ownershipTableData = [];
  const rowMapping = [
    displayedShareholdersWithRatio[0]?.name || "",
    displayedShareholdersWithRatio[1]?.name || "",
    displayedShareholdersWithRatio[2]?.name || "",
    "기타특관자",
    "자사주",
    "기타주주",
    `${mezzTypeEng || "CB"}(당사)`,
    `${mezzTypeEng || "CB"}(공동투자자)`,
    "기발행 메자닌",
    "합계",
  ];

  for (const targetName of rowMapping) {
    if (!targetName) {
      ownershipTableData.push(Array(11).fill(""));
      continue;
    }

    const rowData = [targetName];
    let foundInCases = false;

    for (let index = 0; index < 5; index += 1) {
      const ownershipCase = ownershipCases[index];
      if (!ownershipCase) {
        rowData.push("", "");
        continue;
      }

      const row = ownershipCase.rows.find((item) => item.name === targetName);
      const shares = targetName === "합계" ? ownershipCase.totalShares : row?.shares || 0;
      const ratio = ownershipCase.denominatorShares > 0 ? (shares / ownershipCase.denominatorShares) * 100 : 0;

      if (shares > 0 || targetName === "합계") {
        foundInCases = true;
        rowData.push(shares.toLocaleString());
        rowData.push(`${ratio.toFixed(1)}%`);
      } else {
        rowData.push("-", "-");
      }
    }

    const derivedRow = targetName !== "합계"
      && targetName !== "자사주"
      && targetName !== "기타주주"
      && !targetName.includes("(당사)")
      && !targetName.includes("(공동투자자)")
      && targetName !== "기발행 메자닌";
    ownershipTableData.push(!foundInCases && derivedRow ? Array(11).fill("") : rowData);
  }

  return ownershipTableData;
}

function buildPptData({ inputs, companyInfo, excelData, aiText = {}, ownership = {} }) {
  const mezzType = getMezzType(inputs.mezz_type_full);
  const derived = makeDerivedCompanyFields(companyInfo, excelData, inputs);
  const maxShareholders = parseInteger(ownership.maxShareholders) || 10;
  const displayedShareholdersWithRatio = buildDisplayedShareholders(companyInfo.shareholders || [], maxShareholders);
  const ownershipCases = buildOwnershipCases({
    totalIssuedShares: companyInfo.totalIssuedShares || 0,
    exercisePrice: derived.exercisePrice,
    issueAmt: inputs.issue_amt || "",
    investmentAmt: inputs.investment_amt || "",
    priorMezzanineShares: ownership.priorMezzanineShares || "",
    callPercent: ownership.callPercent || "",
    refixingPercent: ownership.refixingPercent || "",
    displayedShareholdersWithRatio,
    shareholderClassification: companyInfo.shareholderClassification || [],
    isTreasuryEb: Boolean(ownership.isTreasuryEb),
    mezzTypeEng: mezzType.eng,
    newIssuedShares: derived.newIssuedShares,
  });

  let investAmt = String(inputs.investment_amt || "").replace(/,/g, "").trim();
  if (String(inputs.investment_amt || "").includes("억원")) investAmt = "100";

  const data = {
    corp_name: companyInfo.corp_name || "",
    name_end: derived.nameEnd,
    corp_name_full: companyInfo.corp_name_full || "",
    stock_market: companyInfo.stock_market || "",
    stock_code: inputs.stock_code || "",
    mezz_type_kor: mezzType.kor,
    mezz_type_eng: mezzType.eng,
    mezz_type: inputs.mezz_type_full || "",
    invest_amt: !Number.isNaN(Number(investAmt)) ? Number(investAmt).toLocaleString() : investAmt,
    issue_amt: !Number.isNaN(Number(String(inputs.issue_amt || "").replace(/,/g, ""))) ? Number(String(inputs.issue_amt || "").replace(/,/g, "")).toLocaleString() : inputs.issue_amt || "",
    market_cap: excelData.latest_market_cap ? Math.round(excelData.latest_market_cap / 100_000_000).toLocaleString() : "",
    ex_prc: derived.exercisePrice ? derived.exercisePrice.toLocaleString() : "",
    report_date: derived.reportDate,
    base_date: derived.baseDate,
    call_percent: ownership.callPercent || "",
    refixing_percent: ownership.refixingPercent || "",
    corp_summary: "",
    investment_text_title1: aiText.investment_text_title1 || "",
    investment_text_contents1_1: aiText.investment_text_contents1_1 || "",
    investment_text_contents1_2: aiText.investment_text_contents1_2 || "",
    investment_text_title2: aiText.investment_text_title2 || "",
    investment_text_contents2_1: aiText.investment_text_contents2_1 || "",
    investment_text_contents2_2: aiText.investment_text_contents2_2 || "",
    investment_text_title3: aiText.investment_text_title3 || "",
    investment_text_contents3_1: aiText.investment_text_contents3_1 || "",
    investment_text_contents3_2: aiText.investment_text_contents3_2 || "",
    price_text_title1: aiText.price_text_title1 || "",
    price_text_title2: aiText.price_text_title2 || "",
    risk_text_title1: aiText.risk_text_title1 || "",
    risk_text_contents1_1: aiText.risk_text_contents1_1 || "",
    risk_text_title2: aiText.risk_text_title2 || "",
    risk_text_contents2_1: aiText.risk_text_contents2_1 || "",
    premium_text: derived.premiumText,
  };

  for (const [index, shareholder] of displayedShareholdersWithRatio.entries()) {
    data[`sh_name_${index + 1}`] = shareholder.name;
    data[`sh_relation_${index + 1}`] = shareholder.relation;
    data[`sh_shares_${index + 1}`] = shareholder.shares;
    data[`sh_ratio_${index + 1}`] = shareholder.ratio;
  }

  data.ownershipTableData = buildOwnershipTableData({
    displayedShareholdersWithRatio,
    ownershipCases,
    mezzTypeEng: mezzType.eng,
  });

  return {
    data,
    companyInfo: {
      ...companyInfo,
      mezzTypeKor: mezzType.kor,
      mezzTypeEng: mezzType.eng,
      reportDate: derived.reportDate,
      baseDate: derived.baseDate,
      premiumText: derived.premiumText,
      exercisePrice: derived.exercisePrice,
      newIssuedShares: derived.newIssuedShares,
    },
    ownershipCases,
    displayedShareholdersWithRatio,
  };
}

module.exports = {
  buildPptData,
  fetchCompanyInfo,
  readExcelData,
  parseNumber,
  parseInteger,
  parseKrwAmount,
};
