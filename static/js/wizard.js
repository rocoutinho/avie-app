// Wizard visual simples: mostra uma etapa do formulário por vez e valida
// os campos da etapa atual antes de avançar. O envio continua sendo um
// único POST no final — não há lógica extra no backend.
document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector("[data-wizard]");
  if (!form) return;

  const steps = Array.from(form.querySelectorAll(".wizard-step"));
  const progressBar = form.querySelector(".wizard-progress-bar");
  const stepLabel = form.querySelector(".wizard-step-label");
  const prevBtn = form.querySelector("[data-wizard-prev]");
  const nextBtn = form.querySelector("[data-wizard-next]");
  const submitBtn = form.querySelector("[data-wizard-submit]");

  // Se o servidor recarregou a página com erros de validação (ex.: consentimento
  // não marcado), abre direto na etapa que contém o erro em vez de voltar
  // para a etapa 1 e esconder o problema.
  const erroredStep = steps.findIndex((step) => step.querySelector(".is-invalid, .text-danger"));
  let current = erroredStep !== -1 ? erroredStep : 0;

  function render() {
    steps.forEach((step, i) => {
      step.hidden = i !== current;
    });
    progressBar.style.width = ((current + 1) / steps.length) * 100 + "%";
    stepLabel.textContent = "Etapa " + (current + 1) + " de " + steps.length;
    prevBtn.classList.toggle("invisible", current === 0);
    const isLast = current === steps.length - 1;
    nextBtn.classList.toggle("d-none", isLast);
    submitBtn.classList.toggle("d-none", !isLast);
  }

  function currentStepIsValid() {
    const fields = steps[current].querySelectorAll("input, textarea, select");
    for (const field of fields) {
      if (!field.checkValidity()) {
        field.reportValidity();
        return false;
      }
    }
    return true;
  }

  function saveParcialLead() {
    // Assim que a pessoa termina a etapa de contato, salva um lead mínimo
    // no CRM — se ela abandonar o formulário nas etapas seguintes (comum em
    // cliques de anúncio), a equipe ainda tem um contato para retomar.
    const get = (name) => {
      const field = form.querySelector('[name="' + name + '"]');
      return field ? field.value : "";
    };
    const payload = {
      csrf_token: get("csrf_token"),
      full_name: get("full_name"),
      email: get("email"),
      phone: get("phone"),
      instagram: get("instagram"),
      source: get("source"),
      utm_source: get("utm_source"),
      utm_medium: get("utm_medium"),
      utm_campaign: get("utm_campaign"),
      utm_content: get("utm_content"),
      utm_term: get("utm_term"),
    };
    if (!payload.full_name || !payload.email) return;
    fetch("/diagnostico/lead-parcial", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(function () {
      // Melhor esforço — se falhar, o envio final do formulário ainda salva tudo.
    });
  }

  nextBtn.addEventListener("click", function () {
    if (!currentStepIsValid()) return;
    if (current === 0) saveParcialLead();
    current = Math.min(current + 1, steps.length - 1);
    render();
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  prevBtn.addEventListener("click", function () {
    current = Math.max(current - 1, 0);
    render();
  });

  render();
});
