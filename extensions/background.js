var config = {
  mode: "fixed_servers",
  rules: {
    singleProxy: {
      scheme: "http",
      host: "p.webshare.io",
      port: 80,
    },
    bypassList: ["<local>"],
  },
};

chrome.proxy.settings.set({ value: config, scope: "regular" }, function () {});

function callbackFn() {
  return {
    authCredentials: {
      username: "igygxfkp-rotate",
      password: "pi2y76jcs808",
    },
  };
}

chrome.webRequest.onAuthRequired.addListener(
  callbackFn,
  { urls: ["<all_urls>"] },
  ["blocking"]
);
