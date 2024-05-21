using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.Mvc.ModelBinding.Validation;
using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using weblog.Models;

namespace weblog.ModelBinders
{
    public class ModelBinderSwitcherProvider : IModelBinderProvider
    {
        public IModelBinder? GetBinder(ModelBinderProviderContext context)
        {
            if (context.Metadata.ModelType != typeof(object))
            {
                return null;
            }

            var subclasses = new[] { typeof(IEnumerable<string>), typeof(Model), typeof(Models.String), typeof(string) };
            var binders = new Dictionary<Type, (ModelMetadata, IModelBinder)>();
            foreach (var type in subclasses)
            {
                var modelMetadata = context.MetadataProvider.GetMetadataForType(type);
                binders[type] = (modelMetadata, context.CreateBinder(modelMetadata, new BindingInfo { BindingSource = new BindingSource("Body", "", false, true) }));
            }

            return new ModelBinderSwitcher(binders);
        }
    }

    public class ModelBinderSwitcher : IModelBinder
    {
        private Dictionary<Type, (ModelMetadata, IModelBinder)> binders;

        public ModelBinderSwitcher(Dictionary<Type, (ModelMetadata, IModelBinder)> binders)
        {
            this.binders = binders;
        }

        public async Task BindModelAsync(ModelBindingContext bindingContext)
        {


            bindingContext.HttpContext.Request.EnableBuffering();
            foreach (var binderandmetadata in binders.Values)
            {
                var (modelMetadata, binder) = binderandmetadata;
                bindingContext.ModelMetadata = modelMetadata;
                bindingContext.FieldName = string.Empty;
                try
                {
                    bindingContext.HttpContext.Request.Body.Seek(0, SeekOrigin.Begin);
                    bindingContext.ModelState.Clear();
                    await binder.BindModelAsync(bindingContext).ConfigureAwait(false);
                    if (bindingContext.Result != ModelBindingResult.Failed())
                    {
                        if (bindingContext.Result.Model is IValidable validable)
                        {
                            if (!validable.IsValid())
                            {
                                continue;
                            }
                        }

                        // Setting the ValidationState ensures properties on derived types are correctly
                        if (bindingContext.Result.Model != null)
                        {
                            bindingContext.ValidationState[bindingContext.Result.Model] = new ValidationStateEntry
                            {
                                Metadata = modelMetadata,
                            };
                        }

                        return;
                    }
                }
                catch (Exception)
                {
                    continue;
                }
            }
        }
    }
}
