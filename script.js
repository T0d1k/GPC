const header = document.querySelector(".site-header");
const menuToggle = document.querySelector(".menu-toggle");
const nav = document.querySelector(".nav");
const navLinks = document.querySelectorAll('.nav a, .footer-nav a, .btn[href^="#"]');
const fadeItems = document.querySelectorAll(".fade-in");
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const contactForm = document.querySelector("#contact-form");
const formStatus = document.querySelector("#form-status");
const submitButton = contactForm?.querySelector('button[type="submit"]');
const submitButtonLabel = submitButton?.textContent ?? "Contact Us";
const formSendingMessage = contactForm?.dataset.sending ?? "Sending...";
const formErrorMessage = contactForm?.dataset.error ?? "Something went wrong. Please try again.";

function closeMenu() {
  if (!nav || !menuToggle) {
    return;
  }

  nav.classList.remove("open");
  menuToggle.classList.remove("active");
  menuToggle.setAttribute("aria-expanded", "false");
}

function handleHeaderScroll() {
  if (!header) {
    return;
  }

  header.classList.toggle("scrolled", window.scrollY > 20);
}

function scrollToTarget(target) {
  if (!target) {
    return;
  }

  const headerOffset = header ? header.offsetHeight + 12 : 0;
  const top = target.getBoundingClientRect().top + window.scrollY - headerOffset;

  window.scrollTo({
    top,
    behavior: prefersReducedMotion ? "auto" : "smooth"
  });
}

handleHeaderScroll();
window.addEventListener("scroll", handleHeaderScroll);

if (menuToggle && nav) {
  menuToggle.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("open");
    menuToggle.classList.toggle("active", isOpen);
    menuToggle.setAttribute("aria-expanded", String(isOpen));
  });

  document.addEventListener("click", (event) => {
    const clickedInsideMenu = nav.contains(event.target);
    const clickedToggle = menuToggle.contains(event.target);

    if (!clickedInsideMenu && !clickedToggle) {
      closeMenu();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 760) {
      closeMenu();
    }
  });
}

navLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    const href = link.getAttribute("href");

    if (!href || !href.startsWith("#")) {
      return;
    }

    const target = document.querySelector(href);

    if (!target) {
      return;
    }

    event.preventDefault();
    scrollToTarget(target);
    closeMenu();
  });
});

if (prefersReducedMotion) {
  fadeItems.forEach((item) => item.classList.add("visible"));
} else {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.18
  });

  fadeItems.forEach((item) => observer.observe(item));
}

if (contactForm && submitButton && formStatus) {
  const contactEndpoint = window.location.protocol === "file:"
    ? "http://127.0.0.1:8000/api/contact"
    : "/api/contact";

  contactForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!contactForm.reportValidity()) {
      return;
    }

    const formData = new FormData(contactForm);
    const payload = new URLSearchParams();

    formData.forEach((value, key) => {
      payload.append(key, String(value));
    });

    formStatus.textContent = "";
    formStatus.className = "form-status";
    submitButton.disabled = true;
    submitButton.textContent = formSendingMessage;
    contactForm.setAttribute("aria-busy", "true");

    try {
      const response = await fetch(contactEndpoint, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
        },
        body: payload.toString()
      });

      const result = await response.json().catch(() => null);

      if (!response.ok || !result?.ok) {
        throw new Error(result?.message || formErrorMessage);
      }

      formStatus.textContent = result.message || "Your message has been sent.";
      formStatus.classList.add("is-success");
      contactForm.reset();
    } catch (error) {
      formStatus.textContent = error.message || formErrorMessage;
      formStatus.classList.add("is-error");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = submitButtonLabel;
      contactForm.removeAttribute("aria-busy");
    }
  });
}
