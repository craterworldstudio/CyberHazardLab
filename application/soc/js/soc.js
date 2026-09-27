/*
 * Cyber Hazard Lab
 * Security Operations Center
 *
 * Frontend shell only.
 * Backend integration comes later.
 */


document.addEventListener("DOMContentLoaded", () => {

    const navItems = document.querySelectorAll(".nav-item");
    const views = document.querySelectorAll(".soc-view");
    const viewButtons = document.querySelectorAll("[data-view-target]");


    function showView(viewName) {

        views.forEach((view) => {
            view.classList.remove("active");
        });


        const targetView = document.getElementById(
            `view-${viewName}`
        );

        if (!targetView) {
            return;
        }

        targetView.classList.add("active");


        navItems.forEach((item) => {

            item.classList.toggle(
                "active",
                item.dataset.view === viewName
            );

        });

    }


    navItems.forEach((item) => {

        item.addEventListener("click", () => {

            const viewName = item.dataset.view;

            if (!viewName) {
                return;
            }

            showView(viewName);

        });

    });


    viewButtons.forEach((button) => {

        button.addEventListener("click", () => {

            const viewName = button.dataset.viewTarget;

            if (!viewName) {
                return;
            }

            showView(viewName);

        });

    });

});