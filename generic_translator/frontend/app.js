const languageNames = {
  en: "English",
  de: "German",
  fr: "French",
  es: "Spanish",
  it: "Italian",
  pt: "Portuguese",
  nl: "Dutch",
  pl: "Polish"
};


// =========================
// MODE SWITCHING
// =========================

const textModeBtn =
  document.getElementById("textModeBtn");

const documentModeBtn =
  document.getElementById("documentModeBtn");

const emailModeBtn =
  document.getElementById("emailModeBtn");


const textTranslation =
  document.getElementById("textTranslation");

const documentTranslation =
  document.getElementById("documentTranslation");

const emailTranslation =
  document.getElementById("emailTranslation");


function showMode(mode) {

  textTranslation.classList.add("hidden");
  documentTranslation.classList.add("hidden");
  emailTranslation.classList.add("hidden");

  textModeBtn.classList.remove("active");
  documentModeBtn.classList.remove("active");
  emailModeBtn.classList.remove("active");


  if (mode === "text") {

    textTranslation.classList.remove("hidden");

    textModeBtn.classList.add("active");

  }


  else if (mode === "document") {

    documentTranslation.classList.remove("hidden");

    documentModeBtn.classList.add("active");

  }


  else if (mode === "email") {

    emailTranslation.classList.remove("hidden");

    emailModeBtn.classList.add("active");

  }

}


textModeBtn.addEventListener(
  "click",
  () => {
    showMode("text");
  }
);


documentModeBtn.addEventListener(
  "click",
  () => {
    showMode("document");
  }
);


emailModeBtn.addEventListener(
  "click",
  () => {
    showMode("email");
  }
);


// =========================
// GET SELECTED LANGUAGES
// =========================

function getSelectedLanguages(containerId) {

  return [
    ...document.querySelectorAll(
      `#${containerId} input[type="checkbox"]:checked`
    )
  ].map(
    checkbox => checkbox.value
  );

}


// =========================
// HTML ESCAPING
// =========================

function escapeHtml(value) {

  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

}


// =========================
// TEXT TRANSLATION
// =========================

const normalTranslateBtn =
  document.getElementById(
    "normalTranslateBtn"
  );

const normalStatus =
  document.getElementById(
    "normalStatus"
  );

const normalResultsSection =
  document.getElementById(
    "normalResultsSection"
  );

const normalResults =
  document.getElementById(
    "normalResults"
  );


normalTranslateBtn.addEventListener(
  "click",
  async () => {

    const text =
      document.getElementById(
        "normalText"
      ).value;


    const targets =
      getSelectedLanguages(
        "textTargetLanguages"
      );


    if (!text.trim()) {

      normalStatus.textContent =
        "Please enter some text to translate.";

      return;
    }


    if (!targets.length) {

      normalStatus.textContent =
        "Please select at least one target language.";

      return;
    }


    normalTranslateBtn.disabled = true;

    normalStatus.textContent =
      "Translating...";

    normalResultsSection.classList.add(
      "hidden"
    );

    normalResults.innerHTML = "";


    try {

      const response =
        await fetch(
          "/api/translate",
          {
            method: "POST",

            headers: {
              "Content-Type": "application/json"
            },

            body: JSON.stringify({
              subject: "",
              body: text,
              targets: targets,
              source_language: null
            })
          }
        );


      const data =
        await response.json();


      if (!response.ok) {

        throw new Error(
          data.detail ||
          "Translation failed."
        );

      }


      data.results.forEach(
        item => {

          const language =
            languageNames[item.language] ||
            item.language;


          const translatedText =
            item.body || "";


          const card =
            document.createElement(
              "article"
            );


          card.className =
            "translation";


          card.innerHTML = `

            <h3>
              ${escapeHtml(language)}
            </h3>

            <div class="body-box">
              ${escapeHtml(translatedText)}
            </div>

            <div class="actions">

              <button
                class="secondary download-text-btn"
                type="button"
              >
                Download
              </button>

            </div>

          `;


          card
            .querySelector(
              ".download-text-btn"
            )
            .addEventListener(
              "click",
              () => {

                const blob =
                  new Blob(
                    [translatedText],
                    {
                      type:
                        "text/plain;charset=utf-8"
                    }
                  );


                const url =
                  URL.createObjectURL(
                    blob
                  );


                const link =
                  document.createElement(
                    "a"
                  );


                link.href = url;

                link.download =
                  `translated-${item.language}.txt`;


                document.body.appendChild(
                  link
                );

                link.click();

                link.remove();


                URL.revokeObjectURL(
                  url
                );

              }
            );


          normalResults.appendChild(
            card
          );

        }
      );


      normalResultsSection.classList.remove(
        "hidden"
      );


      normalStatus.textContent =
        `Done — ${data.results.length} translation(s) created.`;

    }

    catch (error) {

      normalStatus.textContent =
        error.message;

    }

    finally {

      normalTranslateBtn.disabled =
        false;

    }

  }
);


// =========================
// DOCUMENT TRANSLATION
// =========================

const documentTranslateBtn =
  document.getElementById(
    "documentTranslateBtn"
  );


const documentFile =
  document.getElementById(
    "documentFile"
  );


const documentFileStatus =
  document.getElementById(
    "documentFileStatus"
  );


const documentStatus =
  document.getElementById(
    "documentStatus"
  );


const documentResultsSection =
  document.getElementById(
    "documentResultsSection"
  );


const documentResults =
  document.getElementById(
    "documentResults"
  );


// =========================
// DOCUMENT FILE SELECTION
// =========================

documentFile.addEventListener(
  "change",
  () => {

    if (!documentFile.files.length) {

      documentFileStatus.classList.add(
        "hidden"
      );

      documentFileStatus.classList.remove(
        "file-ready"
      );

      documentFileStatus.innerHTML =
        "";

      return;
    }


    const file =
      documentFile.files[0];


    const sizeMB =
      (
        file.size /
        (1024 * 1024)
      ).toFixed(2);


    documentFileStatus.classList.remove(
      "hidden"
    );

    documentFileStatus.classList.add(
      "file-ready"
    );


    documentFileStatus.innerHTML = `

      <div class="file-check">
        ✓
      </div>

      <div class="file-info">

        <div class="file-success">
          Document selected successfully
        </div>

        <div class="file-name">

          ${escapeHtml(file.name)}

          <span class="file-size">
            · ${sizeMB} MB
          </span>

        </div>

      </div>

    `;

  }
);


// =========================
// DOCUMENT TRANSLATION
// =========================

documentTranslateBtn.addEventListener(
  "click",
  async () => {

    const targets =
      getSelectedLanguages(
        "documentTargetLanguages"
      );


    if (!documentFile.files.length) {

      documentStatus.textContent =
        "Please select a Word (.docx) file.";

      return;
    }


    if (!targets.length) {

      documentStatus.textContent =
        "Please select at least one target language.";

      return;
    }


    const file =
      documentFile.files[0];


    if (
      !file.name
        .toLowerCase()
        .endsWith(".docx")
    ) {

      documentStatus.textContent =
        "Only Word (.docx) files are supported.";

      return;
    }


    documentTranslateBtn.disabled =
      true;


    documentStatus.textContent =
      "Translating document...";


    documentResultsSection.classList.add(
      "hidden"
    );


    documentResults.innerHTML =
      "";


    try {

      for (
        const targetLanguage of targets
      ) {

        documentStatus.textContent =
          `Translating document to ${
            languageNames[targetLanguage]
          }...`;


        const formData =
          new FormData();


        formData.append(
          "file",
          file
        );


        formData.append(
          "target_language",
          targetLanguage
        );


        const response =
          await fetch(
            "/api/translate-document",
            {
              method: "POST",
              body: formData
            }
          );


        if (!response.ok) {

          let errorMessage =
            `Document translation to ${
              languageNames[targetLanguage]
            } failed.`;


          try {

            const data =
              await response.json();


            errorMessage =
              data.detail ||
              errorMessage;

          }

          catch (_) {

            // Keep default message.

          }


          throw new Error(
            errorMessage
          );

        }


        const blob =
          await response.blob();


        const url =
          URL.createObjectURL(
            blob
          );


        const card =
          document.createElement(
            "article"
          );


        card.className =
          "translation";


        card.innerHTML = `

          <h3>
            ${escapeHtml(
              languageNames[targetLanguage]
            )}
          </h3>

          <div class="actions">

            <button
              class="secondary document-download-btn"
              type="button"
            >
              Download ${
                escapeHtml(
                  languageNames[targetLanguage]
                )
              } Document
            </button>

          </div>

        `;


        card
          .querySelector(
            ".document-download-btn"
          )
          .addEventListener(
            "click",
            () => {

              const link =
                document.createElement(
                  "a"
                );


              link.href =
                url;


              link.download =
                `translated-${targetLanguage}-${file.name}`;


              document.body.appendChild(
                link
              );


              link.click();


              link.remove();

            }
          );


        documentResults.appendChild(
          card
        );

      }


      documentResultsSection.classList.remove(
        "hidden"
      );


      documentStatus.textContent =
        `Done — ${
          targets.length
        } translated document(s) created.`;

    }

    catch (error) {

      documentStatus.textContent =
        error.message;

    }

    finally {

      documentTranslateBtn.disabled =
        false;

    }

  }
);


// =========================
// EMAIL TRANSLATION
// =========================

const translateBtn =
  document.getElementById(
    "translateBtn"
  );


const statusEl =
  document.getElementById(
    "status"
  );


const resultsSection =
  document.getElementById(
    "resultsSection"
  );


const resultsEl =
  document.getElementById(
    "results"
  );


// =========================
// OUTLOOK URL
// =========================

function outlookUrl(
  recipient,
  subject,
  body
) {

  const params = [];


  if (recipient.trim()) {

    params.push(
      `to=${encodeURIComponent(
        recipient.trim()
      )}`
    );

  }


  params.push(
    `subject=${encodeURIComponent(
      subject
    )}`
  );


  params.push(
    `body=${encodeURIComponent(
      body
    )}`
  );


  return (
    "https://outlook.office.com/mail/deeplink/compose?" +
    params.join("&")
  );

}


// =========================
// EMAIL TRANSLATION
// =========================

translateBtn.addEventListener(
  "click",
  async () => {

    const subject =
      document.getElementById(
        "subject"
      ).value;


    const body =
      document.getElementById(
        "body"
      ).value;


    const sourceLanguage =
      document.getElementById(
        "sourceLanguage"
      ).value;


    const recipient =
      document.getElementById(
        "recipient"
      ).value;


    const targets =
      getSelectedLanguages(
        "emailTargetLanguages"
      );


    if (
      !subject.trim() &&
      !body.trim()
    ) {

      statusEl.textContent =
        "Please enter the email subject or body.";

      return;
    }


    if (!targets.length) {

      statusEl.textContent =
        "Please select at least one target language.";

      return;
    }


    translateBtn.disabled =
      true;


    statusEl.textContent =
      "Translating...";


    resultsSection.classList.add(
      "hidden"
    );


    resultsEl.innerHTML =
      "";


    try {

      const response =
        await fetch(
          "/api/translate",
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
              subject,
              body,
              targets,
              source_language:
                sourceLanguage || null
            })
          }
        );


      const data =
        await response.json();


      if (!response.ok) {

        throw new Error(
          data.detail ||
          "Translation failed."
        );

      }


      data.results.forEach(
        item => {

          const card =
            document.createElement(
              "article"
            );


          card.className =
            "translation";


          const subjectText =
            item.subject ||
            "(No subject)";


          const bodyText =
            item.body ||
            "";


          card.innerHTML = `

            <h3>
              ${escapeHtml(
                languageNames[item.language] ||
                item.language
              )}
            </h3>

            <div class="subject-box">
              ${escapeHtml(
                subjectText
              )}
            </div>

            <div class="body-box">
              ${escapeHtml(
                bodyText
              )}
            </div>

            <div class="actions">

              <button
                class="secondary copy-btn"
                type="button"
              >
                Copy
              </button>

              <button
                class="outlook outlook-btn"
                type="button"
              >
                Open in Outlook
              </button>

            </div>

          `;


          // COPY BUTTON

          card
            .querySelector(
              ".copy-btn"
            )
            .addEventListener(
              "click",
              async () => {

                const copyText =
                  `${subjectText}\n\n${bodyText}`;


                try {

                  await navigator.clipboard.writeText(
                    copyText
                  );


                  statusEl.textContent =
                    `${
                      languageNames[
                        item.language
                      ] ||
                      item.language
                    } translation copied.`;

                }

                catch (error) {

                  statusEl.textContent =
                    "Unable to copy translation.";

                }

              }
            );


          // OUTLOOK BUTTON

          card
            .querySelector(
              ".outlook-btn"
            )
            .addEventListener(
              "click",
              () => {

                const url =
                  outlookUrl(
                    recipient,
                    subjectText,
                    bodyText
                  );


                window.open(
                  url,
                  "_blank",
                  "noopener,noreferrer"
                );

              }
            );


          resultsEl.appendChild(
            card
          );

        }
      );


      resultsSection.classList.remove(
        "hidden"
      );


      statusEl.textContent =
        `Done — ${
          data.results.length
        } translation(s) created.`;

    }

    catch (error) {

      statusEl.textContent =
        error.message;

    }

    finally {

      translateBtn.disabled =
        false;

    }

  }
);


// =========================
// DEFAULT MODE
// =========================

showMode("text");