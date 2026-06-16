const assert = require("assert");
const test = require("node:test");

const { renderPresentationXml } = require("../electron/ppt-forger");

test("renderPresentationXml replaces scalar placeholders", () => {
  const xml = "<a:t>{{corp_name}}</a:t><a:t>X%</a:t><a:t>Y%</a:t>";
  const rendered = renderPresentationXml(xml, {
    corp_name: "테스트",
    call_percent: "30",
    refixing_percent: "70",
  });

  assert.equal(rendered, "<a:t>테스트</a:t><a:t>30%</a:t><a:t>70%</a:t>");
});
