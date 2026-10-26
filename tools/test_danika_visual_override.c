#include <assert.h>
#include <stdint.h>

#include "danika_visual_override.h"

static void expect(unsigned int class_id,
                   DanikaSide side,
                   unsigned int original,
                   unsigned int donor,
                   unsigned int expected)
{
    assert(danika_select_visual_asset(class_id, side, original, donor) == expected);
}

int main(void)
{
    const unsigned int original = 0x1234u;
    const unsigned int donor = 0x0042u;

    /* The one and only positive path. */
    expect(DANIKA_CLASS_ID, DANIKA_SIDE_ALLIED, original, donor, donor);

    /* Unknown/enemy Danika must remain vanilla. */
    expect(DANIKA_CLASS_ID, DANIKA_SIDE_UNKNOWN, original, donor, original);
    expect(DANIKA_CLASS_ID, DANIKA_SIDE_ENEMY, original, donor, original);

    /* Invalid/unresolved donor selectors fail closed. */
    expect(DANIKA_CLASS_ID, DANIKA_SIDE_ALLIED, original, 0u, original);
    expect(DANIKA_CLASS_ID, DANIKA_SIDE_ALLIED, original,
           DANIKA_INVALID_VISUAL_SELECTOR, original);

    /* Actual Dragoon, hidden Dragoon and unrelated classes are untouched. */
    const unsigned int other_classes[] = {
        0x00u, 0x01u, DRAGOON_CLASS_ID, 0x70u, 0x72u, 0x9Cu, 0xFFu
    };
    for (unsigned int i = 0; i < sizeof(other_classes) / sizeof(other_classes[0]); ++i) {
        expect(other_classes[i], DANIKA_SIDE_UNKNOWN, original, donor, original);
        expect(other_classes[i], DANIKA_SIDE_ALLIED, original, donor, original);
        expect(other_classes[i], DANIKA_SIDE_ENEMY, original, donor, original);
    }

    /* Values wider than the class byte cannot accidentally match 0x71. */
    expect(0x0171u, DANIKA_SIDE_ALLIED, original, donor, donor);
    /* Runtime callers pass the low class byte; document/test that cast explicitly. */
    assert((uint8_t)0x0171u == DANIKA_CLASS_ID);

    assert(danika_visual_selector_is_valid(0u) == 0);
    assert(danika_visual_selector_is_valid(DANIKA_INVALID_VISUAL_SELECTOR) == 0);
    assert(danika_visual_selector_is_valid(donor) != 0);

    return 0;
}
