document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("application-form");
  const successMessage = document.getElementById("success-message");

  if (!form) return;

  const requiredFieldIds = [
    "fullName",
    "workEmail",
    "phone",
    "companyName",
    "industry",
    "companySize",
    "budget",
    "timeline",
    "projectDetails",
  ];

  const validators = {
    fullName: (value) => {
      const text = value.trim();
      if (!text) return "El nombre completo es obligatorio.";
      if (text.length < 3) return "El nombre debe tener al menos 3 caracteres.";
      return "";
    },
    jobTitle: (value) => {
      const text = value.trim();
      if (!text) return "";
      if (text.length < 2) return "El cargo debe tener al menos 2 caracteres.";
      return "";
    },
    workEmail: (value) => {
      const text = value.trim();
      if (!text) return "El email corporativo es obligatorio.";
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(text)) return "Introduce un email valido (ejemplo@empresa.com).";
      return "";
    },
    phone: (value) => {
      const text = value.trim();
      if (!text) return "El telefono es obligatorio.";
      const phoneRegex = /^\+?[0-9\s()-]{9,20}$/;
      if (!phoneRegex.test(text)) return "Introduce un telefono valido con 9 a 20 digitos/caracteres.";
      return "";
    },
    companyName: (value) => {
      const text = value.trim();
      if (!text) return "El nombre de la empresa es obligatorio.";
      if (text.length < 2) return "La empresa debe tener al menos 2 caracteres.";
      return "";
    },
    companyWebsite: (value) => {
      const text = value.trim();
      if (!text) return "";
      try {
        const parsed = new URL(text);
        if (!["http:", "https:"].includes(parsed.protocol)) {
          return "La URL debe empezar por http:// o https://.";
        }
      } catch {
        return "Introduce una URL valida (https://tuempresa.com).";
      }
      return "";
    },
    industry: (value) => {
      if (!value) return "Selecciona el sector de tu empresa.";
      return "";
    },
    companySize: (value) => {
      if (!value) return "Selecciona el tamano de tu empresa.";
      return "";
    },
    budget: (value) => {
      if (!value) return "Selecciona un rango de presupuesto.";
      return "";
    },
    timeline: (value) => {
      if (!value) return "Selecciona el tiempo objetivo de inicio.";
      return "";
    },
    projectDetails: (value) => {
      const text = value.trim();
      if (!text) return "Describe el reto principal que quieres resolver.";
      if (text.length < 20) return "El detalle del reto debe tener al menos 20 caracteres.";
      return "";
    },
  };

  function setFieldError(fieldId, message) {
    const field = document.getElementById(fieldId);
    const errorNode = document.getElementById(`error-${fieldId}`);

    if (!field || !errorNode) return;

    errorNode.textContent = message;

    if (message) {
      field.classList.add("border-red-500", "bg-red-50");
      field.classList.remove("border-slate-300");
      field.setAttribute("aria-invalid", "true");
    } else {
      field.classList.remove("border-red-500", "bg-red-50");
      field.classList.add("border-slate-300");
      field.setAttribute("aria-invalid", "false");
    }
  }

  function setGroupError(groupName, message) {
    const errorNode = document.getElementById(`error-${groupName}`);
    if (!errorNode) return;

    errorNode.textContent = message;
  }

  function validateField(fieldId) {
    const field = document.getElementById(fieldId);
    const validate = validators[fieldId];

    if (!field || !validate) return true;

    const message = validate(field.value);
    setFieldError(fieldId, message);

    return !message;
  }

  function validateServices() {
    const checked = form.querySelectorAll('input[name="services"]:checked').length;
    const message = checked > 0 ? "" : "Selecciona al menos un servicio.";
    setGroupError("services", message);

    return !message;
  }

  function validatePriorityArea() {
    const selected = form.querySelector('input[name="priorityArea"]:checked');
    const message = selected ? "" : "Selecciona un area prioritaria.";
    setGroupError("priorityArea", message);

    return !message;
  }

  function validatePrivacyConsent() {
    const field = document.getElementById("privacyConsent");
    const errorNode = document.getElementById("error-privacyConsent");

    if (!field || !errorNode) return true;

    const message = field.checked ? "" : "Debes aceptar el tratamiento de datos para continuar.";
    errorNode.textContent = message;

    return !message;
  }

  function validateAll() {
    const fieldResults = requiredFieldIds.map((id) => validateField(id));

    validateField("jobTitle");
    validateField("companyWebsite");

    const servicesValid = validateServices();
    const priorityAreaValid = validatePriorityArea();
    const privacyValid = validatePrivacyConsent();

    return fieldResults.every(Boolean) && servicesValid && priorityAreaValid && privacyValid;
  }

  function hideSuccess() {
    successMessage.classList.add("hidden");
  }

  requiredFieldIds.forEach((id) => {
    const field = document.getElementById(id);
    if (!field) return;

    field.addEventListener("input", () => {
      hideSuccess();
      validateField(id);
    });

    field.addEventListener("blur", () => {
      validateField(id);
    });
  });

  ["jobTitle", "companyWebsite"].forEach((id) => {
    const field = document.getElementById(id);
    if (!field) return;

    field.addEventListener("input", () => {
      hideSuccess();
      validateField(id);
    });

    field.addEventListener("blur", () => {
      validateField(id);
    });
  });

  form.querySelectorAll('input[name="services"]').forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      hideSuccess();
      validateServices();
    });
  });

  form.querySelectorAll('input[name="priorityArea"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      hideSuccess();
      validatePriorityArea();
    });
  });

  const privacyConsent = document.getElementById("privacyConsent");
  if (privacyConsent) {
    privacyConsent.addEventListener("change", () => {
      hideSuccess();
      validatePrivacyConsent();
    });
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    hideSuccess();

    const isValid = validateAll();

    if (!isValid) {
      const firstError = form.querySelector('[aria-invalid="true"], #error-services:not(:empty), #error-priorityArea:not(:empty), #error-privacyConsent:not(:empty)');
      if (firstError && typeof firstError.scrollIntoView === "function") {
        firstError.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      return;
    }

    form.reset();

    [
      ...requiredFieldIds,
      "jobTitle",
      "companyWebsite",
    ].forEach((id) => setFieldError(id, ""));

    setGroupError("services", "");
    setGroupError("priorityArea", "");
    const privacyError = document.getElementById("error-privacyConsent");
    if (privacyError) privacyError.textContent = "";

    successMessage.classList.remove("hidden");
    successMessage.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  form.addEventListener("reset", () => {
    [
      ...requiredFieldIds,
      "jobTitle",
      "companyWebsite",
    ].forEach((id) => setFieldError(id, ""));

    setGroupError("services", "");
    setGroupError("priorityArea", "");

    const privacyError = document.getElementById("error-privacyConsent");
    if (privacyError) privacyError.textContent = "";

    hideSuccess();
  });
});
