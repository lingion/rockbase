PROBE_JS = r"""(() => {
  const host = document.querySelector("#efluns-info-anchor") || document.querySelector("#efluns-info-sidebar-anchor");
  if (!host || !host.shadowRoot) {
    return { status: "retry", note: "EasyKOL面板未注入", email: "", hostFound: false, sectionFound: false, sectionText: "" };
  }
  const emailSection = [...host.shadowRoot.querySelectorAll("section")].find(
    s => /邮箱/.test(s.querySelector("header")?.textContent || "")
  );
  if (!emailSection) {
    return { status: "retry", note: "EasyKOL邮箱区块缺失", email: "", hostFound: true, sectionFound: false, sectionText: "" };
  }
  const sectionText = (emailSection.querySelector(".section-body")?.textContent || "").replace(/\s+/g, "").trim();
  const emails = [...new Set(sectionText.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi) || [])];
  if (emails[0]) {
    return { status: "hit", note: "EasyKOL获取", email: emails[0], hostFound: true, sectionFound: true, sectionText };
  }
  if (!sectionText) {
    return { status: "pending_empty", note: "邮箱区块已出现但仍为空", email: "", hostFound: true, sectionFound: true, sectionText };
  }
  return { status: "retry", note: "EasyKOL结果待人工复核", email: "", hostFound: true, sectionFound: true, sectionText };
})()"""
